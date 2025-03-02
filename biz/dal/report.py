import uuid
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Text, Boolean, ForeignKey, TIMESTAMP, CheckConstraint, ARRAY, ENUM
)

from sqlalchemy.dialects.postgresql import UUID,JSONB
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from .base import Base

OAuthProviderEnum = ENUM('google', name='oauth_provider_enum')
CategoriesEnum = ENUM('essential', 'non-essential', name='categories_enum')
ActionEnum = ENUM('change category', 'delete', 'reply', name='action_enum')

class UserPreference(Base):
    __tablename__ = 'user_preferences'
    __table_args__ = {'comment': 'Stores user preferences for email tags'}

    user_id = Column(
        UUID,
        ForeignKey('users.user_id', ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        comment='References the user (from users table) who owns these preferences'
    )
    tags = Column(
        ARRAY(String),
        nullable=False,
        comment='Array of tags the user prefers'
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        comment='Timestamp when the preference was first created'
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment='Timestamp when the preference was last updated'
    )

class Email(Base):
    __tablename__ = 'emails'
    __table_args__ = (
        CheckConstraint("oauth_provider IN ('google')", name='oauth_provider_check'),
        {'comment': 'Stores metadata and content of emails fetched from OAuth providers'}
    )

    email_id = Column(
        UUID,
        primary_key=True,
        default=uuid.uuid4,
        comment='Unique identifier for the email'
    )
    user_id = Column(
        UUID,
        ForeignKey('users.user_id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment='References the user (from users table) who owns this email'
    )
    message_id = Column(
        String(128),
        unique=True,
        nullable=False,
        comment='Unique identifier for the email from the OAuth provider'
    )
    oauth_provider = Column(
        String(16),
        nullable=False,
        comment='The OAuth provider used to fetch the email (currently only Google is supported)'
    )
    thread_id = Column(
        String(128),
        comment='Identifier for the email thread (if applicable)'
    )
    label_ids = Column(
        ARRAY(String),
        comment='Array of labels assigned to the email by the OAuth provider'
    )
    internal_date = Column(
        TIMESTAMP(timezone=True),
        comment='Internal timestamp provided by the OAuth provider'
    )
    sender = Column(
        String(255),
        comment='Email address of the sender'
    )
    recipients = Column(
        Text,
        comment='List of recipients for the email'
    )
    subjects = Column(
        Text,
        comment='Subject line of the email'
    )
    received_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment='Timestamp when the email was received'
    )
    tags = Column(
        ARRAY(String),
        comment='Array of tags assigned to the email'
    )
    category = Column(
        CategoriesEnum,
        nullable=False,
        comment='Category of the email: essential or non-essential'
    )
    summary = Column(
        Text,
        nullable=False,
        comment='Summary of the email content provided by the LLM'
    )
    user_action = Column(
        ActionEnum,
        comment='Action taken by the user on the email (e.g., delete, reply)'
    )
    llm_action_suggest = Column(
        ActionEnum,
        nullable=False,
        comment='Action suggested by the LLM for the email'
    )
    is_deleted = Column(
        Boolean,
        default=False,
        comment='Indicates whether the email is marked as deleted by the user'
    )
    is_processed = Column(
        Boolean,
        default=False,
        comment='Indicates whether the email has been processed by the LLM'
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        comment='Timestamp when the email record was created'
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment='Timestamp when the email record was last updated'
    )

class Report(Base):
    __tablename__ = 'reports'
    __table_args__ = {'comment': 'Stores LLM-generated reports in JSONB format'}

    report_id = Column(
        UUID,
        primary_key=True,
        default=uuid.uuid4,
        comment='Unique identifier for the report'
    )
    user_id = Column(
        UUID,
        ForeignKey('users.user_id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment='References the user (from users table) who generated the report'
    )
    content = Column(
        JSONB,
        nullable=False,
        comment='JSONB content of the report, storing structured data'
    )
    is_deleted = Column(
        Boolean,
        default=False,
        comment='Indicates whether the report is marked as deleted by the user'
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        comment='Timestamp when the report was created'
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment='Timestamp when the report was last updated'
    )

    @classmethod
    def get_latest_report(cls, session: Session, user_id: UUID):
        return (
            session.query(cls)
            .filter_by(user_id=user_id)
            .order_by(cls.created_at.desc())
            .first()
        )

    @classmethod
    def create_blank_report(cls, session: Session, user_id: UUID):
        blank_report = cls(
            user_id=user_id,
            content={"status": "generating"}
        )
        session.add(blank_report)
        session.flush()
        return blank_report

    @classmethod
    def update_content(cls, session: Session, report_id: UUID, content: Dict):
        report = session.query(cls).get(report_id)
        if not report:
            raise ValueError("Report not found")
        report.content = content
        session.flush()
        return report

    @classmethod
    def get_newest_by_user(cls, session: Session, user_id: UUID):
        return (
            session.query(cls)
            .filter_by(user_id=user_id, is_deleted=False)
            .order_by(cls.created_at.desc())
            .first()
        )

    @classmethod
    def list_by_user(cls, session: Session, user_id: UUID):
        return (
            session.query(cls)
            .filter_by(user_id=user_id, is_deleted=False)
            .order_by(cls.created_at.desc())
            .all()
        )
