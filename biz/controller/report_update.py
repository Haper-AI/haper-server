import json
from typing import List

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.prompts import ChatPromptTemplate
from msgraph.generated.models.message import Message

from biz.controller.gmail_util import RawGmailInfo, extract_gmail_info
from biz.controller.outlook_util import extract_outlook_info
from biz.dal.email import Email, EmailSource
from biz.dal.report import MessageCategory, MessageAction, Report
from biz.dal.user_setting import UserSetting
from biz.model.report.rich_text import rich_text_from_dict
from biz.service.db import get_session
from biz.model.report import report as report_model
from biz.utils import schema_loader

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
            "address": "grant.x@gmail.com"
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
            "address": "Alice.Brown@gmail.com"
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
            "address": "Josn.Han@gmail.com"
        }
    },
    {
        "type": "text",
        "text": {
            "content": " discussing your essay topics."
        }
    },
])

summarize_email_prompt_template = ChatPromptTemplate.from_template(
    """
    You are a Email Analysis Agent which can accurately grasp the content of an email by 
    analyzing the sender's address, subject, and body.
    
    
    Guidelines:
      1. Generate insightful email summaries within {words_limit} words.
    
      2. Generate a list of tags about the email
    
      3. Must output the result in json format that contains those keys: 
        - summary: string value, the summary text of current email
        - tags: array of string value, a list of tag about current email
      
      4. Output do not include any explanation, additional text or markdown characters. Return JSON only.
      
    Given Email:
      - Sender: {email_sender}
      - Subject: {email_subject}
      - Body: {email_body}
      - Marked Promotion: {email_marked_promotion}
    """
)

classify_email_prompt_template = ChatPromptTemplate.from_template(
    """
    You are a Email Analysis Agent which can accurately grasp the content of an email by 
    analyzing the sender's address, subject, and body.
    
    
    Guidelines:
      1. Classify an email into one of those categories: {fixed_categories}
        2.2 Current user is more focused on those emails tags: {user_key_tags}
        2.3 If current user has no focused email tags, you may pay more attention to those messages:
          - Work-related messages
          - Financial updates
          - Urgent notifications
          - Personal correspondence
          - Scheduled events
      
      2. Generate one of those actions for current email: {fixed_actions}
      
      3. If there are the memory about the category and action for similar email of current user, you should also 
      take those information into consideration. Each memory item will include:
        - email sender
        - email subject
        - email summary
        - user confirmed category
        - user confirmed action
      
      4. Must output the result in json format that contains those keys:
        - category: string value, the category of the current email"
        - action: string value, the action of the current email"
        
      5. Output do not include any explanation, additional text or markdown characters. Return JSON only.
    
    
    History of users emails:
    {history_examples}
    
    Given Email:
      - Sender: {email_sender}
      - Subject: {email_subject}
      - Marked Promotion: {email_marked_promotion}
      - Summary: {summary_by_llm}
      - Tags: {tags_by_llm}
    """
)

update_summary_template = ChatPromptTemplate.from_template(
    """
    Based on the Current Summary info and New Incoming New Messages info, update and generate the new summary.
    
    Guidelines:
      1. Summary is an array of RichText, and those RichText can be combined into a readable sentences. 
    
      2. Should Strictly follow the json schema of RichText, here is the json schema definition:
      {rich_text_schema}
    
      3. Here is an example of summary:
      {example_summary}
    
      4. New Incoming Messages are a list of json object, for each item, it includes:
        - sender_name
        - sender_email
        - subject
        - summary
        - tags
      
      5. You must output the result as a list of RichText json objects. And in order to kep summary concise, try to 
      combine some RichText if possible. Do not include any explanation, additional text or markdown characters. 
      Return JSON only. 
    
    
    Current Summary:
    {current_summary}
    
    New Incoming New Messages:
    {new_incoming_new_messages}
    """
)


def update_report_with_gmail_message(user_id: str, account_id: str, account_email: str, report_id: str,
                                     gmail_list: List[RawGmailInfo]):
    with get_session(write=False) as session:
        # get user focused tags
        user_setting = UserSetting.get_by_user_id(session, user_id)
        if user_setting is None:
            user_key_tags = []
        else:
            user_key_tags = user_setting.key_message_tags

    # define llm model
    chat_model = init_chat_model("gpt-4o-mini", model_provider="openai")
    embedding_model = init_embeddings("text-embedding-3-small", provider="openai", dimensions=768)

    fixed_categories = json.dumps([MessageCategory.Essential, MessageCategory.NonEssential])
    fixed_actions = json.dumps([MessageAction.Read, MessageAction.Delete, MessageAction.Reply])
    user_key_tags = json.dumps(user_key_tags)

    # the email records that need to insert into the db
    email_db_records: List[Email] = []

    mail_report_item_list: List[report_model.MailMessageItem] = []
    info_for_report_summary_update: List[dict] = []
    for raw_gmail in gmail_list:
        extracted_gmail = extract_gmail_info(raw_gmail.raw_email)

        # use llm to inference
        # generate summary and tags from email
        formated_prompt = summarize_email_prompt_template.format(
            words_limit=50,
            email_sender=extracted_gmail.sender,
            email_subject=extracted_gmail.subject,
            email_body=extracted_gmail.body,
            email_marked_promotion=extracted_gmail.marked_promotion,
        )
        email_summary_response = chat_model.invoke(formated_prompt)
        email_summary_json = json.loads(email_summary_response.content)

        # get embedding for summary
        summary_embedding = embedding_model.embed_query(email_summary_json['summary'])

        # get similar email history
        with get_session(write=False) as session:
            email_history = Email.list_by_similarity(session, user_id, summary_embedding)

        history_examples = None
        if email_history:
            history_examples_json_list = [json.dumps({
                "sender": e.sender,
                "subject": e.subject,
                "summary": e.summary,
                "category": e.modified_category if e.modified_category else e.llm_category,
                "action": e.modified_action if e.modified_action else e.llm_action,
            }, ensure_ascii=False) for e in email_history]

            history_examples = "\n    ".join([f'  - {e}' for e in history_examples_json_list])

        # generate suggested category and action for email
        formated_prompt = classify_email_prompt_template.format(
            fixed_categories=fixed_categories,
            user_key_tags=user_key_tags,
            fixed_actions=fixed_actions,
            history_examples=history_examples,
            email_sender=extracted_gmail.sender,
            email_subject=extracted_gmail.subject,
            email_marked_promotion=extracted_gmail.marked_promotion,
            summary_by_llm=email_summary_json["summary"],
            tags_by_llm=email_summary_json["tags"],
        )
        classify_response = chat_model.invoke(formated_prompt)
        classify_json = json.loads(classify_response.content)

        email_db_records.append(
            Email(
                user_id=user_id,
                source=EmailSource.Gmail,
                message_id=raw_gmail.message_id,
                thread_id=raw_gmail.thread_id,
                sender=extracted_gmail.sender,
                receiver=extracted_gmail.to,
                subject=extracted_gmail.subject,
                received_at=extracted_gmail.receive_at,
                tags=email_summary_json["tags"],
                summary=email_summary_json["summary"],
                summary_embedding=summary_embedding,
                llm_category=classify_json["category"],
                llm_action=classify_json["action"]
            )
        )

        mail_report_item = report_model.MailMessageItem(
            id=0,
            action=classify_json["action"],
            message_id=raw_gmail.message_id,
            thread_id=raw_gmail.thread_id,
            receive_at=extracted_gmail.receive_at,
            sender=extracted_gmail.sender,
            subject=extracted_gmail.subject,
            summary=email_summary_json["summary"],
            category=classify_json["category"],
            tags=email_summary_json["tags"],
            action_result=None,
            reply_message=None,
        )
        mail_report_item_list.append(mail_report_item)
        if classify_json["category"] == MessageCategory.Essential:
            info_for_report_summary_update.append({
                "sender_name": extracted_gmail.sender_name,
                "sender_email": extracted_gmail.sender_email,
                "subject": extracted_gmail.subject,
                "summary": email_summary_json["summary"],
                "tags": email_summary_json["tags"],
            })

    with get_session(write=False) as session:
        # get report
        report = Report.get_by_id(session, report_id)

    # update report
    report_obj = report_model.report_from_dict(report.content)

    ## update report summary using llm if needed
    if info_for_report_summary_update:
        formated_prompt = update_summary_template.format(
            rich_text_schema=schema_loader.rich_text_schema,
            example_summary=example_summary,
            current_summary=json.dumps([r.to_dict() for r in report_obj.summary], ensure_ascii=False),
            new_incoming_new_messages=json.dumps(info_for_report_summary_update, ensure_ascii=False)
        )
        report_summary_response = chat_model.invoke(formated_prompt)
        report_summary_json = json.loads(report_summary_response.content)
        report_obj.summary = [rich_text_from_dict(r) for r in report_summary_json]

    ## update report content
    if report_obj.content.content_sources is None:
        report_obj.content.content_sources = []
    if EmailSource.Gmail not in report_obj.content.content_sources:
        report_obj.content.content_sources.append(EmailSource.Gmail)

    if report_obj.content.gmail is None:
        report_obj.content.gmail = []

    mail_report_item_list_by_account = None
    for v in report_obj.content.gmail:
        if v.account_id == account_id:
            mail_report_item_list_by_account = v
            break

    if mail_report_item_list_by_account is None:
        mail_report_item_list_by_account = report_model.MailMessagesByAccount(
            account_id=account_id,
            email=account_email,
            messages=[]
        )
        report_obj.content.gmail.append(mail_report_item_list_by_account)

    with get_session(write=True) as session:
        session.add_all(email_db_records)
        session.flush()

        for email_record, mail_report_item in zip(email_db_records, mail_report_item_list):
            mail_report_item._id = email_record.id

        mail_report_item_list_by_account.messages.extend(mail_report_item_list)

        # re-fetch report and update report messages_in_queue as messages_in_queue
        # will also be updated by webhooks so there may be some concurrency issue
        # as for summary and content part, as only will consumer update those,
        # and messages with same report_id will be handled by same consumer as we are
        # using fifo sqs queue right now, there will be no concurrency issue for those two parts.
        messages_in_queue = Report.get_content_subfield(
            session,
            report_id,
            content_subfield_key="messages_in_queue",
            for_update=True
        )
        messages_in_queue[EmailSource.Gmail] -= len(gmail_list)
        report_obj.messages_in_queue = messages_in_queue
        Report.update(session, report_id, content=report_obj.to_dict())


def update_report_with_outlook_emails(user_id: str, account_id: str, account_email: str, report_id: str,
                                     outlook_emails: List[Message]):
    with get_session(write=False) as session:
        # get user focused tags
        user_setting = UserSetting.get_by_user_id(session, user_id)
        if user_setting is None:
            user_key_tags = []
        else:
            user_key_tags = user_setting.key_message_tags

    # define llm model
    chat_model = init_chat_model("gpt-4o-mini", model_provider="openai")
    embedding_model = init_embeddings("text-embedding-3-small", provider="openai", dimensions=768)

    fixed_categories = json.dumps([MessageCategory.Essential, MessageCategory.NonEssential])
    fixed_actions = json.dumps([MessageAction.Read, MessageAction.Delete, MessageAction.Reply])
    user_key_tags = json.dumps(user_key_tags)

    # the email records that need to insert into the db
    email_db_records: List[Email] = []

    mail_report_item_list: List[report_model.MailMessageItem] = []
    info_for_report_summary_update: List[dict] = []
    for raw_email in outlook_emails:
        extracted_outlook = extract_outlook_info(raw_email)

        # use llm to inference
        # generate summary and tags from email
        formated_prompt = summarize_email_prompt_template.format(
            words_limit=50,
            email_sender=extracted_outlook.sender,
            email_subject=extracted_outlook.subject,
            email_body=extracted_outlook.body,
            email_marked_promotion="Unknown",
        )
        email_summary_response = chat_model.invoke(formated_prompt)
        email_summary_json = json.loads(email_summary_response.content)

        # get embedding for summary
        summary_embedding = embedding_model.embed_query(email_summary_json['summary'])

        # get similar email history
        with get_session(write=False) as session:
            email_history = Email.list_by_similarity(session, user_id, summary_embedding)

        history_examples = None
        if email_history:
            history_examples_json_list = [json.dumps({
                "sender": e.sender,
                "subject": e.subject,
                "summary": e.summary,
                "category": e.modified_category if e.modified_category else e.llm_category,
                "action": e.modified_action if e.modified_action else e.llm_action,
            }, ensure_ascii=False) for e in email_history]

            history_examples = "\n    ".join([f'  - {e}' for e in history_examples_json_list])

        # generate suggested category and action for email
        formated_prompt = classify_email_prompt_template.format(
            fixed_categories=fixed_categories,
            user_key_tags=user_key_tags,
            fixed_actions=fixed_actions,
            history_examples=history_examples,
            email_sender=extracted_outlook.sender_email,
            email_subject=extracted_outlook.subject,
            email_marked_promotion="Unknown",
            summary_by_llm=email_summary_json["summary"],
            tags_by_llm=email_summary_json["tags"],
        )
        classify_response = chat_model.invoke(formated_prompt)
        classify_json = json.loads(classify_response.content)

        email_db_records.append(
            Email(
                user_id=user_id,
                source=EmailSource.Outlook,
                message_id=extracted_outlook.message_id,
                thread_id=extracted_outlook.thread_id,
                sender=extracted_outlook.sender,
                receiver=extracted_outlook.to,
                subject=extracted_outlook.subject,
                received_at=extracted_outlook.receive_at,
                tags=email_summary_json["tags"],
                summary=email_summary_json["summary"],
                summary_embedding=summary_embedding,
                llm_category=classify_json["category"],
                llm_action=classify_json["action"]
            )
        )

        mail_report_item = report_model.MailMessageItem(
            id=0,
            action=classify_json["action"],
            message_id=extracted_outlook.message_id,
            thread_id=extracted_outlook.thread_id,
            receive_at=extracted_outlook.receive_at,
            sender=extracted_outlook.sender,
            subject=extracted_outlook.subject,
            summary=email_summary_json["summary"],
            category=classify_json["category"],
            tags=email_summary_json["tags"],
            action_result=None,
            reply_message=None,
        )
        mail_report_item_list.append(mail_report_item)
        if classify_json["category"] == MessageCategory.Essential:
            info_for_report_summary_update.append({
                "sender_name": extracted_outlook.sender_name,
                "sender_email": extracted_outlook.sender_email,
                "subject": extracted_outlook.subject,
                "summary": email_summary_json["summary"],
                "tags": email_summary_json["tags"],
            })

    with get_session(write=False) as session:
        # get report
        report = Report.get_by_id(session, report_id)

    # update report
    report_obj = report_model.report_from_dict(report.content)

    ## update report summary using llm if needed
    if info_for_report_summary_update:
        formated_prompt = update_summary_template.format(
            rich_text_schema=schema_loader.rich_text_schema,
            example_summary=example_summary,
            current_summary=json.dumps([r.to_dict() for r in report_obj.summary], ensure_ascii=False),
            new_incoming_new_messages=json.dumps(info_for_report_summary_update, ensure_ascii=False)
        )
        report_summary_response = chat_model.invoke(formated_prompt)
        report_summary_json = json.loads(report_summary_response.content)
        report_obj.summary = [rich_text_from_dict(r) for r in report_summary_json]

    ## update report content
    if report_obj.content.content_sources is None:
        report_obj.content.content_sources = []
    if EmailSource.Outlook not in report_obj.content.content_sources:
        report_obj.content.content_sources.append(EmailSource.Outlook)

    if report_obj.content.outlook is None:
        report_obj.content.outlook = []

    mail_report_item_list_by_account = None
    for v in report_obj.content.outlook:
        if v.account_id == account_id:
            mail_report_item_list_by_account = v
            break

    if mail_report_item_list_by_account is None:
        mail_report_item_list_by_account = report_model.MailMessagesByAccount(
            account_id=account_id,
            email=account_email,
            messages=[]
        )
        report_obj.content.outlook.append(mail_report_item_list_by_account)

    with get_session(write=True) as session:
        session.add_all(email_db_records)
        session.flush()

        for email_record, mail_report_item in zip(email_db_records, mail_report_item_list):
            mail_report_item._id = email_record.id

        mail_report_item_list_by_account.messages.extend(mail_report_item_list)

        # re-fetch report and update report messages_in_queue as messages_in_queue
        # will also be updated by webhooks so there may be some concurrency issue
        # as for summary and content part, as only will consumer update those,
        # and messages with same report_id will be handled by same consumer as we are
        # using fifo sqs queue right now, there will be no concurrency issue for those two parts.
        messages_in_queue = Report.get_content_subfield(
            session,
            report_id,
            content_subfield_key="messages_in_queue",
            for_update=True
        )
        messages_in_queue[EmailSource.Outlook] -= len(outlook_emails)
        report_obj.messages_in_queue = messages_in_queue
        Report.update(session, report_id, content=report_obj.to_dict())
