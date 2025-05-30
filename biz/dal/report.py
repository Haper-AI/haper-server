import uuid
from typing import Dict, Union

from sqlalchemy import Column, ForeignKey, TIMESTAMP, String, cast

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
    Ignore = "Ignore"


class ReportStatus(str, PyEnum):
    Appending = "Appending"
    Finalized = "Finalized"


class ReportType(str, PyEnum):
    Realtime = "Realtime"
    Previous = "Previous"


class Report(Base):
    __tablename__ = 'reports'
    __table_args__ = {'comment': 'Message report'}

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
    type = Column(
        String(16),
        nullable=False,
        comment='Type of the report, e.g., Realtime or Previous'
    )
    status = Column(
        String(16),
        nullable=False,
        comment='Status of the report itself'
    )
    content = Column(
        JSONB,
        nullable=False,
        comment='JSONB content of the report, storing structured data'
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
    last_access_at = Column(
        TIMESTAMP(timezone=True),
        comment='Timestamp when the report was last read by the user'
    )
    deleted_at = Column(
        TIMESTAMP(timezone=True),
        comment='Timestamp when the report was marked as deleted by the user'
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment='Timestamp when the report was last updated'
    )

    @classmethod
    def add(cls, session: Session, user_id: Union[str, UUID], report_type: ReportType, content: dict):
        blank_report = cls(
            user_id=user_id,
            type=report_type,
            status=ReportStatus.Appending,
            content=content
        )
        session.add(blank_report)
        session.flush()
        return blank_report

    @classmethod
    def update(cls, session: Session, report_id: Union[str, UUID],
               status: ReportStatus = None, content: Dict = None, update_last_access_at: bool = False):
        updates = {}
        if status:
            updates['status'] = status
            if status == ReportStatus.Finalized:
                updates['finalized_at'] = func.now()
        if content:
            updates['content'] = content
        if update_last_access_at:
            updates['last_access_at'] = func.now()
        session.query(cls).filter_by(id=report_id).update(updates)

    @classmethod
    def update_content_subfield(cls, session: Session, report_id: Union[str, UUID],
                                content_subfield_key: str, content_subfield_value: dict):
        session.query(cls).filter_by(id=report_id).update({
            'content': func.jsonb_set(
                cls.content,
                [content_subfield_key],
                cast(content_subfield_value, JSONB)
            )
        })

    @classmethod
    def get_content_subfield(cls, session: Session, report_id: Union[str, UUID], content_subfield_key: str,
                             for_update=False):
        q = session.query(cls.content[content_subfield_key]).filter_by(id=report_id)
        if for_update:
            q = q.with_for_update()
        return q.first()[0]

    @classmethod
    def get_by_id(cls, session: Session, report_id: Union[str, UUID], for_update=False):
        q = session.query(cls).filter_by(id=report_id)
        if for_update:
            q = q.with_for_update()
        return q.first()

    @classmethod
    def get_latest_by_user_id(cls, session: Session, user_id: Union[str, UUID], report_type: ReportType,
                              for_update=False):
        q = (session.query(cls)
             .filter_by(user_id=user_id, type=report_type, status=ReportStatus.Appending)
             .order_by(cls.created_at.desc())
             )
        if for_update:
            q = q.with_for_update()
        return q.first()

    @classmethod
    def count_by_user(cls, session: Session, user_id: Union[str, UUID]):
        return (
            session.query(cls)
            .filter_by(user_id=user_id, deleted_at=None, status=ReportStatus.Finalized)
            .count()
        )

    @classmethod
    def list_by_user(cls, session: Session, user_id: Union[str, UUID], page: int, page_size: int):
        return (
            session.query(cls)
            .filter_by(user_id=user_id, deleted_at=None, status=ReportStatus.Finalized)
            .order_by(cls.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

    @classmethod
    def mark_deleted(cls, session: Session, report_id: Union[str, UUID]):
        session.query(cls).filter_by(id=report_id).update({'deleted_at': func.now()})

    @classmethod
    def delete(cls, session: Session, report_id: Union[str, UUID]):
        session.query(cls).filter_by(id=report_id).delete()
