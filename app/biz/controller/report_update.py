from typing import List, Dict
from datetime import datetime
import json
from app.db.models import Report
from app.db.session import get_session

def generate_report_with_gmail_message(
    user_id: str,
    account_id: str,
    email: str,
    report_id: str,
    emails: List[RawGmailInfo],
    total_messages: int
):
    """
    Generate a new report from historical Gmail messages.
    """
    with get_session(write=True) as session:
        # Create new report
        report = Report(
            user_id=user_id,
            account_id=account_id,
            email=email,
            content=json.dumps({
                "gmail": [{
                    "account_id": account_id,
                    "messages": [email.to_dict() for email in emails]
                }],
                "outlook": []
            }),
            total_messages=total_messages,
            created_at=datetime.utcnow()
        )
        session.add(report)
        session.commit()

def generate_report_with_outlook_emails(
    user_id: str,
    account_id: str,
    email: str,
    report_id: str,
    emails: List[Dict],
    total_messages: int
):
    """
    Generate a new report from historical Outlook messages.
    """
    with get_session(write=True) as session:
        # Create new report
        report = Report(
            user_id=user_id,
            account_id=account_id,
            email=email,
            content=json.dumps({
                "gmail": [],
                "outlook": [{
                    "account_id": account_id,
                    "messages": emails
                }]
            }),
            total_messages=total_messages,
            created_at=datetime.utcnow()
        )
        session.add(report)
        session.commit()