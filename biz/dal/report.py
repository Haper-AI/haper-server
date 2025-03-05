import uuid
from typing import Dict, Union

from sqlalchemy import Column, Boolean, ForeignKey, TIMESTAMP, String

from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from .base import Base

from enum import Enum as PyEnum


class MessageCategory(str, PyEnum):
    Essential = "Essential"
    NonEssential = "NonEssential"


class MessageAction(str, PyEnum):
    Read = "Read"
    Delete = "Delete"
    Reply = "Reply"


class ReportStatus(str, PyEnum):
    Appending = "Appending"
    Finalized = "Finalized"


class Report(Base):
    __tablename__ = 'reports'
    __table_args__ = {'comment': 'Message Report data'}

    id = Column(
        UUID,
        primary_key=True,
        default=uuid.uuid4,
        comment='Unique identifier for the report'
    )
    user_id = Column(
        UUID,
        ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment='References the user (from users table) who generated the report'
    )
    status = Column(
        String(16),
        nullable=False,
        comment='Status of the report'
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
    finalized_at = Column(
        TIMESTAMP(timezone=True),
        comment='Timestamp when the report was finalized'
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment='Timestamp when the report was last updated'
    )

    @classmethod
    def add(cls, session: Session, user_id: Union[str, UUID], content: dict):
        blank_report = cls(
            user_id=user_id,
            status=ReportStatus.Appending,
            content=content
        )
        session.add(blank_report)
        session.flush()
        return blank_report

    @classmethod
    def update(cls, session: Session, report_id: Union[str, UUID],
               status: ReportStatus = None, content: Dict = None):
        updates = {}
        if status:
            updates['status'] = status
            if status == ReportStatus.Finalized:
                updates['finalized_at'] = func.now()
        if content:
            updates['content'] = content
        session.query(cls).filter_by(id=report_id).update(updates)

    @classmethod
    def get_by_id(cls, session: Session, report_id: Union[str, UUID]):
        return session.query(cls).filter_by(id=report_id).first()

    @classmethod
    def get_latest_by_user_id(cls, session: Session, user_id: Union[str, UUID]):
        return (
            session.query(cls)
            .filter_by(user_id=user_id, is_deleted=False, status=ReportStatus.Appending)
            .order_by(cls.created_at.desc())
            .first()
        )

    @classmethod
    def list_by_user(cls, session: Session, user_id: Union[str, UUID]):
        return (
            session.query(cls)
            .filter_by(user_id=user_id, is_deleted=False, status=ReportStatus.Finalized)
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def mark_deleted(cls, session: Session, report_id: Union[str, UUID]):
        session.query(cls).filter_by(id=report_id).update({'is_deleted': True})

    @classmethod
    def delete(cls, session: Session, report_id: Union[str, UUID]):
        session.query(cls).filter_by(id=report_id).delete()