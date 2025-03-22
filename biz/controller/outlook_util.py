from datetime import datetime


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


def extract_outlook_info(email_info: dict):
    extracted_outlook_info = OutlookInfo()
    extracted_outlook_info.message_id = email_info["id"]
    extracted_outlook_info.thread_id = email_info.get("conversationId")
    receive_at_str = email_info["receivedDateTime"]
    extracted_outlook_info.receive_at = datetime.strptime(receive_at_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    sender_info_dict = email_info["sender"]["emailAddress"]
    extracted_outlook_info.sender_name = sender_info_dict["name"]
    extracted_outlook_info.sender_email = sender_info_dict["address"]
    extracted_outlook_info.sender = "{} <{}>".format(extracted_outlook_info.sender_name,
                                                     extracted_outlook_info.sender_email)
    recipient_info_dict = email_info["toRecipients"]["emailAddress"]
    extracted_outlook_info.to = recipient_info_dict["address"]
    extracted_outlook_info.subject = email_info["subject"]
    body_info_dict = email_info["body"]
    extracted_outlook_info.mime_type = body_info_dict["contentType"]
    extracted_outlook_info.body = body_info_dict["content"]

    return extracted_outlook_info
