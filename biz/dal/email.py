from enum import Enum as PyEnum
from typing import List, Union, Optional

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
        {'comment': 'Stores metadata and embedding of emails for RAG'}
    )

    id = Column(
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
    reply_message = Column(
        Text,
        comment='Reply message of the email'
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
    def get_by_id(cls, session: Session, email_id: int):
        return session.query(cls).filter_by(id=email_id).first()

    @classmethod
    def list_by_similarity(cls, session: Session, user_id: Union[str, UUID], summary_embedding: List[float],
                           cosine_distance_boundary: float = 0.2,
                           limit: int = 5,
                           require_reply_message: bool = False,
                           exclude_ids: Optional[List[int]]  = None,
                           ):
        cosine_distance = cls.summary_embedding.cosine_distance(summary_embedding)
        query_fields = [cls.sender, cls.subject, cls.summary, cls.llm_category,
                        cls.modified_category, cls.llm_action, cls.modified_action]
        if require_reply_message:
            query_fields.append(cls.reply_message)
        q = session.query(*query_fields).filter_by(user_id=user_id)
        if require_reply_message:
            q = q.filter(cls.reply_message.isnot(None))
        if exclude_ids:
            q = q.filter(cls.id.not_in(exclude_ids))
        rows = (
            q
            .filter(cosine_distance <= cosine_distance_boundary)
            .order_by(cosine_distance)
            .limit(limit)
            .all()
        )
        results = []
        for r in rows:
            results.append(Email(
                sender=r[0],
                subject=r[1],
                summary=r[2],
                llm_category=r[3],
                modified_category=r[4],
                llm_action=r[5],
                modified_action=r[6],
                reply_message=r[7] if require_reply_message else None,
            ))
        return results

    @classmethod
    def update(cls, session: Session, email_id: int, modified_category: Optional[str] = None,
               modified_action: Optional[str] = None, reply_message: Optional[str] = None, ):
        updates = {}
        if modified_category:
            updates['modified_category'] = modified_category
        if modified_action:
            updates['modified_action'] = modified_action
        if reply_message:
            updates['reply_message'] = reply_message
        if updates:
            session.query(cls).filter_by(id=email_id).update(updates)

    @classmethod
    def delete(cls, session: Session, email_id: int):
        session.query(cls).filter_by(id=email_id).delete()