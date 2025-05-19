from datetime import timedelta
from typing import Optional, List, Union

from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, func, ARRAY, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from .base import Base

DEFAULT_REPORT_MAX_TIME_DURATION = timedelta(days=7).total_seconds()  # default 1 week


class UserSetting(Base):
    __tablename__ = "user_settings"
    __table_args__ = {"comment": "Stores user preferences for message tags"}

    user_id = Column(
        UUID,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
        comment="References the users table id field"
    )

    key_message_tags = Column(
        ARRAY(String(32)),
        comment="User's preferred message tags stored as an array"
    )

    report_max_duration = Column(
        Integer,
        nullable=False,
        comment="Maximum time duration for a report cover in seconds",
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        comment="Timestamp when the user setting was created"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the user setting was last updated"
    )

    @classmethod
    def add(cls, session: Session, user_id: Union[str, UUID], key_message_tags: Optional[List[str]] = None,
            report_max_duration: int = DEFAULT_REPORT_MAX_TIME_DURATION):
        setting = cls(
            user_id=user_id,
            key_message_tags=key_message_tags,
            report_max_duration=report_max_duration,
        )
        session.add(setting)
        session.flush()
        return setting

    @classmethod
    def get_by_user_id(cls, session: Session, user_id: Union[str, UUID]):
        return session.query(cls).filter_by(user_id=user_id).first()

    @classmethod
    def update(cls, session: Session, user_id: str, key_message_tags: Optional[List[str]] = None,
               report_max_duration: Optional[int] = None):
        updates = {}
        if key_message_tags:
            updates["key_message_tags"] = key_message_tags
        if report_max_duration:
            updates["report_max_duration"] = report_max_duration

        if updates:
            session.query(cls).filter_by(user_id=user_id).update(updates)
