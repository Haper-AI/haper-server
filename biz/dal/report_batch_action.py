import uuid
from typing import Union, List

from sqlalchemy import Column, TIMESTAMP, ForeignKey, String, Integer, cast
from sqlalchemy.dialects.mysql import VARCHAR
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from .base import Base

from enum import Enum as PyEnum


class BatchActionRunStatus(str, PyEnum):
    Ongoing = "Ongoing"
    Done = "Done"


class MessageActionResult(str, PyEnum):
    Success = "success"
    Error = "error"


class ReportBatchAction(Base):
    __tablename__ = 'report_batch_actions'
    __table_args__ = {'comment': 'Report batch action run info'}

    id = Column(
        UUID,
        primary_key=True,
        default=uuid.uuid4,
        comment='Unique run id',
    )
    report_id = Column(
        UUID,
        ForeignKey('reports.id', ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment='References the reports table id field',
    )
    status = Column(
        String(16),
        nullable=False,
        comment='Status of the batch action run',
    )
    total_actions = Column(
        Integer,
        nullable=False,
        comment='Total number of actions to run',
    )
    succeed_actions = Column(
        Integer,
        nullable=False,
        default=0,
        comment='Number of successful actions',
    )
    failed_actions = Column(
        Integer,
        nullable=False,
        default=0,
        comment='Number of failed actions',
    )
    logs = Column(
        ARRAY(JSONB),
        comment='Report Batch Action Logs',
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        comment='Timestamp when the batch action was created'
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment='Timestamp when the batch action was last updated'
    )

    @classmethod
    def add(cls, session: Session, report_id: Union[str, UUID], total_actions: int):
        record = cls(
            report_id=report_id,
            status=BatchActionRunStatus.Ongoing,
            total_actions=total_actions,
        )
        session.add(record)
        session.flush()
        return record

    @classmethod
    def get_by_id(cls, session: Session, run_id: Union[str, UUID]):
        return session.query(cls).filter_by(id=run_id).first()

    @classmethod
    def get_latest(cls, session: Session, report_id: Union[str, UUID]):
        return session.query(cls).filter_by(report_id=report_id).order_by(cls.created_at.desc()).first()

    @classmethod
    def append_logs(cls, session: Session, run_id: Union[str, UUID], logs: List[dict]):
        # casted_logs = [cast(l, JSONB) for l in logs]
        session.query(cls).filter_by(id=run_id).update({
            'logs': func.coalesce(cls.logs, []) + logs
        })

    @classmethod
    def increase_success_actions(cls, session: Session, run_id: Union[str, UUID]):
        session.query(cls).filter_by(id=run_id).update({
            'success_actions': cls.succeed_actions + 1
        })

    @classmethod
    def increase_failed_actions(cls, session: Session, run_id: Union[str, UUID]):
        session.query(cls).filter_by(id=run_id).update({
            'failed_actions': cls.failed_actions + 1
        })

    @classmethod
    def update(cls, session: Session, run_id: Union[str, UUID], status: BatchActionRunStatus):
        session.query(cls).filter_by(id=run_id).update({
            'status': status
        })
