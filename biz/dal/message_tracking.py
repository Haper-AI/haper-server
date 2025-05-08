from typing import Optional, Union

from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Session

from enum import Enum as PyEnum

from .base import Base


class MessageTrackingStatus(str, PyEnum):
    NOT_STARTED = "NotStarted"
    ONGOING = "Ongoing"
    STOPPED = "Stopped"
    ERROR = "Error"


class MessageTrackingStatusExtraInfoKeys(str, PyEnum):
    Expiration = "expiration"
    SubscriptionID = "subscription_id"
    PreHistoryID = "pre_history_id"


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
    account_provider = Column(
        String(16),
        nullable=False,
        comment='The OAuth provider, like google, discord, etc. Duplicated filed from accounts table'
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
        server_default=func.now(),
        comment="UTC timestamp when the message tracking record was first created"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="UTC timestamp of the last update to the message tracking record"
    )

    @classmethod
    def add(cls, session: Session, user_id: Union[str, UUID], account_id: Union[str, UUID], account_provider: str,
            extra_info: Optional[dict] = None):
        record = cls(
            user_id=user_id,
            account_id=account_id,
            account_provider=account_provider,
            status=MessageTrackingStatus.ONGOING,
            extra_info=extra_info
        )
        session.add(record)
        session.flush()
        return record

    @classmethod
    def list_by_user_id(cls, session: Session, user_id: Union[str, UUID], ongoing_only: bool = False):
        if ongoing_only:
            return session.query(cls).filter_by(user_id=user_id, status=MessageTrackingStatus.ONGOING).all()
        return session.query(cls).filter_by(user_id=user_id).all()

    @classmethod
    def count_ongoing_by_user_id(cls, session: Session, user_id: Union[str, UUID]):
        return session.query(cls).filter_by(user_id=user_id, status=MessageTrackingStatus.ONGOING).count()

    @classmethod
    def get_by_user_id_and_account_id(cls, session: Session, user_id: Union[str, UUID], account_id: Union[str, UUID],
                                      for_update: bool = False):
        q = session.query(cls).filter_by(user_id=user_id, account_id=account_id)
        if for_update:
            q = q.with_for_update()
        return q.first()

    @classmethod
    def update(cls, session: Session, user_id: Union[str, UUID], account_id: Union[str, UUID],
               status: Optional[MessageTrackingStatus] = None,
               extra_info: Optional[dict] = None):
        updates = {}
        if status:
            updates["status"] = status
        if extra_info:
            updates["extra_info"] = extra_info

        if updates:
            session.query(cls).filter_by(user_id=user_id, account_id=account_id).update(updates)

    @classmethod
    def update_extra_info_subfield(cls, session: Session, user_id: Union[str, UUID], account_id: Union[str, UUID],
                                   extra_info_key: str, extra_info_value: Union[str, int]):
        session.query(cls).filter_by(user_id=user_id, account_id=account_id).update({
            cls.extra_info: func.jsonb_set(cls.extra_info, [extra_info_key], func.to_jsonb(extra_info_value))
        })