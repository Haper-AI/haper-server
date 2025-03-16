import base64
import json
import threading
from datetime import datetime
from typing import Literal, List, Optional, Dict

from googleapiclient.errors import HttpError
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session, make_transient

from biz.controller.gmail_util import extract_gmail_info
from biz.dal.email import Email
from biz.dal.report_batch_action import ReportBatchAction, BatchActionRunStatus, MessageActionResult
from biz.dal.user import Account
from biz.service.db import get_session
from biz.dal.report import Report, ReportStatus, MessageCategory, MessageAction
from biz.utils.gmail import build_gmail_client
from biz.utils.logger import logger
from biz.utils.response import ResponseCode
from biz.model.report import report as report_model
from biz.model.report import action_log as action_log_model


def start_new_reporting_sequence(session: Session, user_id: str):
    latest_report = Report.get_latest_by_user_id(session, user_id)
    if latest_report:
        raise ResponseCode.UnsupportedAction.create_error("already started reporting sequence")

    # create a new blank report
    Report.add(session, user_id, {})


def end_reporting_sequence(session: Session, user_id: str):
    latest_report = Report.get_latest_by_user_id(session, user_id, for_update=True)
    if not latest_report:
        raise ResponseCode.UnsupportedAction.create_error("reporting sequence already ended")
    if not latest_report.content:  # if latest report doesn't have content, delete it directly
        Report.delete(session, latest_report.id)
    else:
        # has content, finalize report
        Report.update(session, latest_report.id, status=ReportStatus.Finalized)


def generate_report(user_id: str):
    with get_session(write=True) as session:
        latest_report = Report.get_latest_by_user_id(session, user_id, for_update=True)
        if latest_report and not latest_report.content:
            raise ResponseCode.UnsupportedAction.create_error(
                "latest report has no content, please wait for new messages")
        # finalize the report and create a new one
        Report.update(session, latest_report.id, status=ReportStatus.Finalized)
        blank_report = Report.add(session, user_id, {})
        make_transient(latest_report), make_transient(blank_report)

    return latest_report, blank_report


def get_newest_report(user_id: str):
    with get_session(write=False) as session:
        latest_report = Report.get_latest_by_user_id(session, user_id)
    return latest_report


def list_history_reports(user_id: str, page: int, page_size: int):
    with get_session(write=False) as session:
        reports = Report.list_by_user(session, user_id, page, page_size)
        count = Report.count_by_user(session, user_id)

    return reports, count


def get_report_by_id(user_id: str, report_id: str):
    with get_session(write=False) as session:
        report = Report.get_by_id(session, report_id)

    if not report or report.is_deleted:
        raise ResponseCode.ResourceNotFound.create_error("report not found")

    if str(report.user_id) != user_id:
        raise ResponseCode.UnsupportedAction.create_error("current user does not has permission for this report")
    return report


def delete_report_by_id(user_id: str, report_id: str):
    with get_session(write=True) as session:
        report = Report.get_by_id(session, report_id, for_update=True)

        if not report or report.is_deleted:
            raise ResponseCode.ResourceNotFound.create_error("report not found")

        if str(report.user_id) != user_id:
            raise ResponseCode.UnsupportedAction.create_error("current user does not has permission for this report")

        if report.status == ReportStatus.Appending:
            raise ResponseCode.UnsupportedAction.create_error("current report is still processing incoming messages")

        Report.mark_deleted(session, report_id)


class ReportUpdateInfo(BaseModel):
    class InfoUpdates(BaseModel):
        id: int
        category: Literal[MessageCategory.Essential, MessageCategory.NonEssential]
        action: Literal[MessageAction.Read, MessageAction.Delete, MessageAction.Reply, MessageAction.Ignore]
        reply_message: Optional[str] = None

    gmail: Dict[str, List[InfoUpdates]]  # key: account id

    @model_validator(mode='after')
    def validate_req(self):
        if len(self.gmail) == 0:
            raise ValueError("empty update info")

        for k, v in self.gmail.items():
            if len(v) == 0:
                raise ValueError(f"empty update info for account {k}")

        return self


def update_report_info(user_id: str, report_id: str, update_info: ReportUpdateInfo):
    with get_session(write=True) as session:
        report = Report.get_by_id(session, report_id, for_update=True)
        if not report:
            raise ResponseCode.InvalidParam.create_error("no report found")

        if str(report.user_id) != user_id:
            raise ResponseCode.UnsupportedAction.create_error("current user does not has permission for this report")

        if report.status == ReportStatus.Appending:
            raise ResponseCode.UnsupportedAction.create_error(
                "can not update report as it still processing incoming messages")

        latest_batch_action = ReportBatchAction.get_latest(session, report_id)
        if latest_batch_action and latest_batch_action.status == BatchActionRunStatus.Ongoing:
            raise ResponseCode.UnsupportedAction.create_error(
                "current report is processing batch actions, please wait for it to complete")

        if not report.content:
            raise ResponseCode.UnsupportedAction.create_error(
                "current report has not content, please wait for new messages")

        report_content_obj = report_model.ReportContent.from_dict(report.content["content"])

        # update gmail
        ## map update_info by account_id, then by id
        mapped_update_info: Dict[str, Dict[int, ReportUpdateInfo.InfoUpdates]] = {}
        for account_id, updates_by_account in update_info.gmail.items():
            if account_id not in mapped_update_info:
                mapped_update_info[account_id] = {}
            for update_info in updates_by_account:
                mapped_update_info[account_id][update_info.id] = update_info

        ## map report_info by
        mapped_report_info: Dict[str, Dict[int, report_model.MailMessageItem]] = {}
        if report_content_obj.gmail:
            for report_items_by_account in report_content_obj.gmail:
                if report_items_by_account.account_id not in mapped_report_info:
                    mapped_report_info[report_items_by_account.account_id] = {}
                for report_item in report_items_by_account.messages:
                    mapped_report_info[report_items_by_account.account_id][report_item.id] = report_item

        for account_id, updates_by_id in mapped_update_info.items():
            for id, update in updates_by_id.items():
                if account_id not in mapped_report_info or id not in mapped_report_info[account_id]:
                    raise ResponseCode.InvalidParam.create_error(
                        f"no corresponding report with id {id} in account {account_id}"
                    )

                gmail_report_item = mapped_report_info[account_id][id]
                if gmail_report_item.action_result == MessageActionResult.Success:
                    raise ResponseCode.UnsupportedAction.create_error(
                        "try to update report item that has successfully done action"
                    )

                modified_category = None
                modified_action = None
                reply_message = None

                # update gmail_report_item
                if gmail_report_item.category != update.category:
                    gmail_report_item.category = update.category
                    modified_category = update.category

                if gmail_report_item.action != update.action:
                    gmail_report_item.action = update.action
                    modified_action = update.action
                    if update.action == MessageAction.Reply and update.reply_message:
                        gmail_report_item.reply_message = update.reply_message
                        reply_message = update.reply_message

                if modified_category or modified_action or reply_message:
                    Email.update(session, id, modified_category=modified_category, modified_action=modified_action,
                                 reply_message=reply_message)

        # update report content
        Report.update_content_subfield(session, report_id, "content", report_content_obj.to_dict())


def do_batch_action(report_id: str, run_id: str):
    """
    the function to apply all available actions in a report, runs in another thread
    :param report_id:
    :param run_id:
    :return:
    """
    try:
        with get_session(write=False) as session:
            report = Report.get_by_id(session, report_id)
            report_obj = report_model.report_from_dict(report.content)

        if report_obj.content.gmail:
            # apply gmail actions
            for messages_by_account in report_obj.content.gmail:
                if messages_by_account.messages:
                    # get account
                    with get_session(write=False) as session:
                        account = Account.get_by_id(session, messages_by_account.account_id)

                    gmail_api_client, credential = build_gmail_client(
                        account.access_token,
                        account.refresh_token,
                        datetime.fromtimestamp(account.expires_at)
                    )

                    for gmail_item in messages_by_account.messages:
                        try:
                            if gmail_item.action_result == MessageActionResult.Success:
                                # skip for already success action
                                continue

                            if gmail_item.action == MessageAction.Read:
                                gmail_api_client.users().messages().modify(
                                    userId='me',
                                    id=gmail_item.message_id,
                                    body={
                                        'removeLabelIds': ['UNREAD'],
                                    }
                                ).execute()
                            elif gmail_item.action == MessageAction.Delete:
                                gmail_api_client.users().messages().trash(
                                    userId='me',
                                    id=gmail_item.message_id,
                                ).execute()
                            elif gmail_item.action == MessageAction.Reply:
                                body_data = base64.urlsafe_b64encode(gmail_item.reply_message.encode("utf-8"))
                                gmail_api_client.users().messages().send(
                                    userId='me',
                                    body={
                                        "threadId": gmail_item.thread_id,
                                        "payload": {
                                            # TODO: support more type of mimeType
                                            "mimeType": "text/plain",
                                            "body": {
                                                "size": len(body_data),
                                                "data": body_data.decode("utf-8")
                                            }
                                        }
                                    }
                                ).execute()

                            # if gmail_item.action == MessageAction.Ignore:
                            # ignore

                            gmail_item.action_result = MessageActionResult.Success
                            log_to_add = action_log_model.ActionLog(
                                at=int(datetime.now().timestamp()),
                                id=gmail_item.id,
                                message=f"{gmail_item.action} {gmail_item.sender} failed",
                            ).to_dict()

                        except Exception as e:
                            logger.error(e)
                            gmail_item.action_result = MessageActionResult.Error
                            log_to_add = action_log_model.ActionLog(
                                at=int(datetime.now().timestamp()),
                                id=gmail_item.id,
                                message=f"{gmail_item.action} {gmail_item.sender} failed",
                            ).to_dict()
                        finally:
                            with get_session(write=True) as session:
                                # insert action log
                                ReportBatchAction.append_logs(session, run_id, [
                                    log_to_add,
                                ])
                                if gmail_item.action_result == MessageActionResult.Success:
                                    ReportBatchAction.increase_success_actions(session, report_id)
                                else:
                                    ReportBatchAction.increase_failed_actions(session, report_id)
                                # update content
                                Report.update_content_subfield(session, report_id, "content",
                                                               report_obj.content.to_dict())

        # set batch run status
        with get_session(write=True) as session:
            ReportBatchAction.update(session, report_id, status=BatchActionRunStatus.Done)

    except Exception as e:
        logger.error(e)


def apply_report_actions(user_id: str, report_id: str):
    with get_session(write=True) as session:
        report = Report.get_by_id(session, report_id)
        if not report:
            raise ResponseCode.InvalidParam.create_error("no report found")

        if str(report.user_id) != user_id:
            raise ResponseCode.UnsupportedAction.create_error("current user does not has permission for this report")

        if report.status == ReportStatus.Appending:
            raise ResponseCode.UnsupportedAction.create_error(
                "batch actions cannot be applied as report still receiving messages")

        # check if there is already a batch action running
        latest_batch_action = ReportBatchAction.get_latest(session, report_id)
        if latest_batch_action and latest_batch_action.status == BatchActionRunStatus.Ongoing:
            raise ResponseCode.UnsupportedAction.create_error(
                "current report is still executing actions, please wait for the last to complete")

        if not report.content:
            raise ResponseCode.UnsupportedAction.create_error(
                "current report has not content, please wait for new messages")

        # check if still has messages to be processed for this report
        report_obj = report_model.report_from_dict(report.content)
        for k, v in report_obj.messages_in_queue.items():
            if v > 0:
                raise ResponseCode.UnsupportedAction.create_error(
                    "current report still has messages in queue to process, please wait for it to complete"
                )

        # get total actions to run
        total_count = 0
        for messages_by_account in report_obj.content.gmail:
            for gmail_item in messages_by_account.messages:
                if gmail_item.action_result != MessageActionResult.Success:
                    if gmail_item.action == MessageAction.Reply and not gmail_item.reply_message:
                        raise ResponseCode.UnsupportedAction.create_error(
                            "message item action is reply but has no reply message")

                    total_count += 1

        if total_count == 0:
            raise ResponseCode.UnsupportedAction.create_error("no actions needed to run for this report")

        # generate a batch run in another thread
        # TODO: should use another consumer or just use faas?
        run = ReportBatchAction.add(session, report_id, total_count)
        t = threading.Thread(target=do_batch_action, args=(report_id, str(run.id)))
        t.start()
        make_transient(run)

    return run.id


def get_latest_batch_action(user_id: str, report_id: str):
    with get_session(write=False) as session:
        report = Report.get_by_id(session, report_id)

    if not report:
        raise ResponseCode.InvalidParam.create_error("no report found")

    if str(report.user_id) != user_id:
        raise ResponseCode.UnsupportedAction.create_error("current user does not has permission for this report")

    batch_run = ReportBatchAction.get_latest(session, report_id=report_id)
    if not batch_run:
        raise ResponseCode.InvalidParam.create_error("current report has no batch action run record")

    return batch_run


def poll_last_batch_action(run_id: str):
    with get_session(write=False) as session:
        return ReportBatchAction.get_by_id(session, run_id)


generate_email_reply_prompt_template = ChatPromptTemplate.from_template(
    """
    Based given email information and the reply history for similar email, generate an email reply
    
    Guidelines:
      1. The reply history could be empty or null. If it's not empty, it will be a list of json objects, for each item, it includes:
        - sender
        - subject
        - summary
        - reply 
    
    Given Email:
      - Sender: {email_sender}
      - Subject: {email_subject}
      - Body: {email_body} 
      
    Reply History:
    {reply_history}
    """
)


def generate_message_reply(user_id: str, report_id: str, source: str, account_id: str, id: int):
    with get_session(write=False) as session:
        report = Report.get_by_id(session, report_id)

    if str(report.user_id) != user_id:
        raise ResponseCode.UnsupportedAction.create_error("current user does not has permission for this report")

    if not report.content or "content" not in report.content or not report.content["content"]:
        raise ResponseCode.UnsupportedAction.create_error("current report has no message content")

    # check if there is already a batch action running
    latest_batch_action = ReportBatchAction.get_latest(session, report_id)
    if latest_batch_action.status == BatchActionRunStatus.Ongoing:
        raise ResponseCode.UnsupportedAction.create_error(
            "current report is executing actions, please wait for the last to complete")

    report_content = report_model.ReportContent.from_dict(report.content["content"])
    if source == "gmail":
        corresponding_gmail_item = None
        for messages_by_account in report_content.gmail:
            if corresponding_gmail_item:
                break
            if messages_by_account.account_id == account_id:
                for gmail_item in messages_by_account.messages:
                    if gmail_item.id == id:
                        if gmail_item.action != MessageAction.Reply:
                            raise ResponseCode.UnsupportedAction.create_error(
                                "the action for current message is not reply"
                            )
                        if gmail_item.action_result == MessageActionResult.Success:
                            raise ResponseCode.UnsupportedAction.create_error(
                                "the action for current message already done")

                        corresponding_gmail_item = gmail_item
                        break

        if not corresponding_gmail_item:
            raise ResponseCode.InvalidParam.create_error("not corresponding gmail message in current report")

        # start generate
        ## retrival relevant email with reply_message
        with get_session(write=False) as session:
            email = Email.get_by_id(session, id)

            email_history = Email.list_by_similarity(session, user_id, email.summary_embedding,
                                                     require_reply_message=True)

        reply_history = None
        if email_history:
            history_email_json_list = [json.dumps({
                "sender": e.sender,
                "subject": e.subject,
                "summary": e.summary,
                "reply_history": e.reply_message,
            }, ensure_ascii=False) for e in email_history]
            reply_history = "\n    ".join([f'  - {e}' for e in history_email_json_list])

        ## get email body
        with get_session(write=False) as session:
            account = Account.get_by_id(session, account_id)

        gmail_api_client, credential = build_gmail_client(
            account.access_token,
            account.refresh_token,
            datetime.fromtimestamp(account.expires_at)
        )
        try:
            raw_email = gmail_api_client.users().messages().get(
                userId="me",
                id=corresponding_gmail_item.message_id,
            )
        except HttpError as e:
            if e.resp.status == 404:
                raise ResponseCode.UnsupportedAction.create_error("email seems has been deleted from your mail box")

        extract_gmail = extract_gmail_info(raw_email)

        formated_prompt = generate_email_reply_prompt_template.format(
            email_sender=corresponding_gmail_item.sender,
            email_subject=corresponding_gmail_item.subject,
            email_body=extract_gmail.body,
            reply_history=reply_history,
        )

        chat_model = init_chat_model("gpt-4o-mini", model_provider="openai")
        for chunk in chat_model.stream(formated_prompt):
            yield chunk
    else:
        raise ResponseCode.UnsupportedAction.create_error("unknown source")
