import base64
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_tz, mktime_tz
from typing import List

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.prompts import ChatPromptTemplate

from biz.dal.email import Email
from biz.dal.report import MessageCategory, MessageAction, Report
from biz.dal.user_setting import UserSetting
from biz.service.db import get_session
from biz.model.report import report as report_model
from biz.utils import schema_loader


class RawGmailInfo:
    def __init__(self, message_id: str, thread_id: str, raw_email: dict):
        self.message_id = message_id
        self.thread_id = thread_id
        self.raw_email = raw_email


class GmailInfo:
    snippet: str
    mime_type: str
    receive_at: datetime
    sender_name: str
    sender_email: str
    subject: str
    body: str

    def __init__(self):
        pass


example_summary = json.dumps([
    {
        "type": "text",
        "text": {
            "content": "You have received 1 invitation from "
        }
    },
    {
        "type": "email",
        "email": {
            "name": "Grant",
            "email": "grant.x@gmail.com"
        }
    },
    {
        "type": "text",
        "text": {
            "content": " about your upcoming trip, 1 reply from "
        }
    },
    {
        "type": "email",
        "email": {
            "name": "Alice Brown",
            "email": "Alice.Brown@gmail.com"
        }
    },
    {
        "type": "text",
        "text": {
            "content": " about your car rental project, 1 email from your professor "
        }
    },
    {
        "type": "email",
        "email": {
            "name": "Josh",
            "email": "Josn.Han@gmail.com"
        }
    },
    {
        "type": "text",
        "text": {
            "content": " discussing your essay topics."
        }
    },
])


def extract_gmail_info(email_info: dict):
    snippet = email_info["snippet"]
    payload = email_info["payload"]
    headers = payload["headers"]
    extracted_gmail_info = GmailInfo()
    extracted_gmail_info.snippet = snippet
    extracted_gmail_info.mime_type = payload["mimeType"]
    for header in headers:
        if header["name"] == "Date":
            raw_date = header["value"]
            parsed_time = parsedate_tz(raw_date)
            extracted_gmail_info.receive_at = datetime.fromtimestamp(mktime_tz(parsed_time), timezone.utc)
        elif header["name"] == "From":
            match = re.match(r"(.+?)\s*<(.+?)>", header['value'])
            if match:
                extracted_gmail_info.sender_name = match.group(1).strip()
                extracted_gmail_info.sender_email = match.group(2).strip()
        elif header["name"] == "Subject":
            extracted_gmail_info.subject = header['value']

    # get email body
    body = ""
    if extracted_gmail_info.mime_type == 'multipart/alternative':
        parts = payload["parts"]
        # prefer html part first
        for part in parts:
            if part["mimeType"] == "text/html":
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                break

        # if not html part, default to use the first part
        if not body:
            body = base64.urlsafe_b64decode(parts[0]["body"]["data"]).decode("utf-8")

    elif extracted_gmail_info.mime_type == "text/plain" or extracted_gmail_info.mime_type == "text/html":
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

    extracted_gmail_info.body = body

    return extracted_gmail_info


summarize_email_prompt_template = ChatPromptTemplate.from_template(
    """
    You are a Email Analysis Agent which can accurately grasp the content of an email by 
    analyzing the sender's address, subject, and body.


    Guidelines:
    1. Generate insightful email summaries within {words_limit} words.
    
    2. Generate a list of tags about the email
    
    3. Must output the result in json format, below is the format definition:
      {
        "summary": "string, the summary of the current email",
        "tags": "string array, the tags of the current email",
      }
    """
)

classify_email_prompt_template = ChatPromptTemplate.from_template(
    """
    You are a Email Analysis Agent which can accurately grasp the content of an email by 
    analyzing the sender's address, subject, and body.


    Guidelines:
    1. Classify an email into one of those categories: [{fixed_categories}]
      2.2 Current user is more focused on those emails tags: [{user_key_tags}]
      2.3 If current user has no focused email tags, you may pay more attention to those messages:
        - Work-related messages
        - Financial updates
        - Urgent notifications
        - Personal correspondence
        - Scheduled events

    2. Generate one of those actions for current email: [{fixed_actions}] 

    3. If there are the memory about the category and action for similar email of current user, you should also 
    take those information into consideration. Each memory item will include:
      - email sender
      - email subject
      - email summary
      - user confirmed category
      - user confirmed action

    4. Must output the result in json format, below is the format definition:
      {
        "category": "string, the category of the current email",
        "action": "string, the action of the current email",
      }


    History of users emails:
    {history_examples}

    Given Email:
    Sender: {email_sender}
    Subject: {email_subject}
    Body: {email_body}
    Summary_by_llm: {summary_by_llm}
    Tags_by_llm: {tags_by_llm}
    """
)

update_summary_template = ChatPromptTemplate.from_template(
    """
    Based on the Current Summary info and New Incoming New Messages info, update and generate the new summary.
    
    Guidelines:
    1. Summary is an array of RichText, and those RichText can be combined into a readable sentences. 
    
    2. Here is the json schema definition of RichText:
    {rich_text_schema}
    
    3. Here is an example of summary:
    {example_summary}
    
    4. New Incoming Messages are a list of json object, for each item, it includes:
      - sender name
      - sender email
      - subject
      - summary
      - tags
      
    5. You must output the result as a list of RichText json objects.
    
    
    Current Summary:
    {current_summary}
    
    New Incoming New Messages
    {new_incoming_new_messages}
    """
)


def update_report_with_gmail_message(user_id: str, report_id: str, gmail_list: List[RawGmailInfo]):
    with get_session(write=False) as session:
        # get user focused tags
        user_key_tags = UserSetting.get_by_user_id(session, user_id).key_message_tags

    # define llm model
    chat_model = init_chat_model("gpt-4o-mini", model_provider="openai")
    embedding_model = init_embeddings("text-embedding-3-small", provider="openai", dimensions=768)

    fixed_categories = ", ".join([MessageCategory.Essential, MessageCategory.NonEssential])
    fixed_actions = ", ".join([MessageAction.Read, MessageAction.Delete, MessageAction.Reply])
    user_key_tags = ", ".join(user_key_tags)

    email_db_record_to_add: List[Email] = []
    essential_gmails: List[report_model.MailReportItem] = []
    non_essential_gmails: List[report_model.MailReportItem] = []
    info_for_report_summary_update: List[dict] = []
    for raw_gmail in gmail_list:
        extracted_gmail = extract_gmail_info(raw_gmail.raw_email)

        # use llm to inference
        # generate summary and tags from email
        summary_response = chat_model.invoke(summarize_email_prompt_template.format(
            words_limit=50,

        ))
        summary_json = json.loads(summary_response.content)

        # get embedding for summary
        summary_embedding = embedding_model.invoke(summary_json['summary'])

        # get similar email history
        with get_session(write=False) as session:
            email_history = Email.list_by_similarity(
                session, user_id, summary_embedding,
                cosine_distance_boundary=0.7, limit=10
            )

        history_examples = None
        if email_history:
            history_examples = "\n".join([json.dumps({
                "sender": e.sender,
                "subject": e.subject,
                "summary": e.summary,
                "category": e.modified_category if e.modified_category else e.llm_category,
                "action": e.modified_action if e.modified_action else e.llm_action,
            }, ensure_ascii=False) for e in email_history])

        # generate suggested category and action for email
        classify_response = chat_model.invoke(classify_email_prompt_template.format(
            fixed_categories=fixed_categories,
            user_key_tags=user_key_tags,
            fixed_actions=fixed_actions,
            history_examples=history_examples,
            email_sender=extracted_gmail.sender_email,
            email_subject=extracted_gmail.subject,
            email_body=extracted_gmail.body,
            summary_by_llm=summary_json["summary"],
            tags_by_llm=summary_json["tags"],
        ))
        classify_json = json.loads(classify_response.content)

        email_db_record_to_add.append(
            Email(
                user_id=user_id,
                source="gmail",
                message_id=raw_gmail.message_id,
                thread_id=raw_gmail.thread_id,
                sender=extracted_gmail.sender_email,
                subject=extracted_gmail.subject,
                received_at=extracted_gmail.receive_at,
                tags=summary_json["tags"],
                summary=summary_json["summary"],
                summary_embedding=summary_embedding,
                llm_category=classify_json["category"],
                llm_action=classify_json["action"]
            )
        )

        mail_report_item = report_model.MailReportItem(
            action=classify_json["action"],
            message_id=raw_gmail.message_id,
            thread_id=raw_gmail.thread_id,
            receive_at=extracted_gmail.receive_at,
            sender=extracted_gmail.sender_email,
            subject=extracted_gmail.subject,
            summary=summary_json["summary"],
            tags=summary_json["tags"]
        )
        if classify_json["category"] == MessageCategory.Essential:
            essential_gmails.append(mail_report_item)
            info_for_report_summary_update.append({
                "sender_name": extracted_gmail.sender_name,
                "sender_email": extracted_gmail.sender_email,
                "subject": extracted_gmail.subject,
                "summary": summary_json["summary"],
                "tags": summary_json["tags"],
            })
        else:
            non_essential_gmails.append(mail_report_item)

    with get_session(write=False) as session:
        # get report
        report = Report.get_by_id(session, report_id)

    # update report
    report_obj = report_model.report_from_dict(report.content)

    ## 1. update report summary using llm
    chat_model.invoke(update_summary_template.format(
        rich_text_schema=schema_loader.rich_text_schema,
        example_summary=example_summary,
        current_summary=json.dumps([r.to_dict() for r in report_obj.summary], ensure_ascii=False),
        new_incoming_new_messages=json.dumps(info_for_report_summary_update, ensure_ascii=False)
    ))

    ## 2. update report content
    if not report_obj.content.content_sources:
        report_obj.content.content_sources = []
    if "gmail" not in report_obj.content.content_sources:
        report_obj.content.content_sources.append("gmail")

    if not report_obj.content.gmail:
        report_obj.content.gmail = report_model.Gmail(essential=[], non_essential=[])

    report_obj.content.gmail.essential.extend(essential_gmails)
    report_obj.content.gmail.non_essential.extend(non_essential_gmails)

    with get_session(write=True) as session:
        session.add_all(email_db_record_to_add)
        Report.update(session, report_id, content=report_obj.to_dict())
