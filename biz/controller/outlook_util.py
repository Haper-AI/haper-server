from datetime import datetime

from msgraph.generated.models.message import Message


class OutlookInfo:
    message_id: str
    thread_id: str
    mime_type: str
    receive_at: datetime
    sender: str
    sender_name: str
    sender_email: str
    to: str
    subject: str
    body: str


def extract_outlook_info(email_info: Message):
    extracted_outlook_info = OutlookInfo()
    extracted_outlook_info.message_id = email_info.id
    extracted_outlook_info.thread_id = email_info.conversation_id
    extracted_outlook_info.receive_at = email_info.received_date_time
    sender_info_dict = email_info.sender.email_address
    extracted_outlook_info.sender_name = sender_info_dict.name
    extracted_outlook_info.sender_email = sender_info_dict.address
    extracted_outlook_info.sender = "{} <{}>".format(extracted_outlook_info.sender_name,
                                                     extracted_outlook_info.sender_email)
    recipient_info_dict = email_info.to_recipients[0].email_address
    extracted_outlook_info.to = recipient_info_dict.address
    extracted_outlook_info.subject = email_info.subject
    body_info_dict = email_info.body
    extracted_outlook_info.mime_type = body_info_dict.content_type
    extracted_outlook_info.body = body_info_dict.content

    return extracted_outlook_info
