from typing import Optional

from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

from enum import Enum as PyEnum

from sqlalchemy.orm import Session

from .base import Base


class MessageTrackingStatus(str, PyEnum):
    NOT_STARTED = "not_started"
    ONGOING = "ongoing"
    STOPPED = "stopped"
    ERROR = "error"


class MessageTrackingRecord(Base):
    __tablename__ = 'message_tracking_records'
    __table_args__ = {'comment': 'Message tracking status of a particular user'}

    user_id = Column(
        UUID,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        comment="References the users table id field"
    )
    account_id = Column(
        UUID,
        ForeignKey("accounts.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        comment="References the accounts table id field"
    )
    status = Column(
        String(16),
        nullable=False,
        comment="The status of the message tracking record"
    )
    error_info = Column(
        Text,
        comment="The error information if the status is error"
    )
    extra_info = Column(
        JSONB,
        comment="Additional information stored as JSONB"
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=func.now(),
        comment="UTC timestamp when the message tracking record was first created"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        comment="UTC timestamp of the last update to the message tracking record"
    )

    @classmethod
    def add(cls, session: Session, user_id: str, account_id: str, extra_info: Optional[dict] = None):
        record = cls(
            user_id=user_id,
            account_id=account_id,
            status=MessageTrackingStatus.ONGOING,
            extra_info=extra_info
        )
        session.add(record)
        session.flush()
        return record

    @classmethod
    def list_by_user_id(cls, session: Session, user_id: str):
        return session.query(cls).filter_by(user_id=user_id).all()

    @classmethod
    def get_by_user_id_and_account_id(cls, session: Session, user_id: str, account_id: str):
        return session.query(cls).filter_by(user_id=user_id, account_id=account_id).first()

    @classmethod
    def update(cls, session: Session, user_id: str, account_id: str,
               status: Optional[MessageTrackingStatus] = None,
               extra_info: Optional[dict] = None):
        updates = {}
        if status:
            updates["status"] = status
        if extra_info:
            updates["extra_info"] = extra_info

        if updates:
            session.query(cls).filter_by(user_id=user_id, account_id=account_id).update(updates)