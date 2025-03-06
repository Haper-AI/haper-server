from enum import Enum as PyEnum
from typing import List, Union

from sqlalchemy import (
    Column,
    UUID,
    ForeignKey,
    String,
    Text,
    TIMESTAMP,
    ARRAY,
    func,
    BigInteger,
    UniqueConstraint
)
from sqlalchemy.orm import Session
from pgvector.sqlalchemy import Vector

from .base import Base


class EmailSource(str, PyEnum):
    Gmail = "gmail"
    Outlook = "outlook"


class Email(Base):
    __tablename__ = 'emails'
    __table_args__ = (
        UniqueConstraint('source', 'message_id', name='unique_email_per_source'),
        {'comment': 'Stores metadata and content of emails fetched from OAuth providers'}
    )

    email_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment='Unique identifier for the email'
    )
    user_id = Column(
        UUID,
        ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment='References the user (from users table) who owns this email'
    )
    source = Column(
        String(16),
        nullable=False,
        comment='The email source like gmail and outlook'
    )
    message_id = Column(
        String(128),
        unique=True,
        nullable=False,
        comment='Unique identifier for the email from the message source'
    )
    thread_id = Column(
        String(128),
        comment='Identifier for the email thread (if applicable)'
    )
    sender = Column(
        String(128),
        nullable=False,
        comment='Name and email address of the sender'
    )
    receiver = Column(
        String(128),
        nullable=False,
        comment='Email address of the receiver'
    )
    subject = Column(
        Text,
        comment='Subject line of the email'
    )
    received_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        comment='Timestamp when the email was received'
    )
    tags = Column(
        ARRAY(Text),
        comment='Array of tags assigned to the email'
    )
    summary = Column(
        Text,
        nullable=False,
        comment='Summary of the email content provided by the LLM'
    )
    summary_embedding = Column(
        Vector(dim=768)
    )
    llm_category = Column(
        String(16),
        nullable=False,
        comment='Category of the email provided by the LLM'
    )
    modified_category = Column(
        String(16),
        comment='Modified category of the email by user'
    )
    llm_action = Column(
        String(16),
        nullable=False,
        comment='Action suggested by the LLM for the email'
    )
    modified_action = Column(
        String(16),
        comment='Modified action taken by the user on the email'
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

    @classmethod
    def list_by_similarity(cls, session: Session, user_id: Union[str, UUID], summary_embedding: List[float],
                           cosine_distance_boundary: float, limit: int):
        cosine_distance = cls.summary_embedding.cosine_distance(summary_embedding)
        return (
            session.query(
                cls.sender,
                cls.subject,
                cls.summary,
                cls.llm_category,
                cls.modified_category,
                cls.llm_action,
                cls.modified_action,
            )
            .filter_by(user_id=user_id)
            .filter(cosine_distance <= cosine_distance_boundary)
            .order_by(cosine_distance)
            .limit(limit)
            .all()
        )
