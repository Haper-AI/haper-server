from sqlalchemy import Column, String, TIMESTAMP, func, SmallInteger
from sqlalchemy.orm import Session

from .base import Base


class PresetMessageTag(Base):
    __tablename__ = "preset_message_tags"
    __table_args__ = {
        "comment": "System preset message tags"
    }

    id = Column(
        SmallInteger,
        primary_key=True,
        autoincrement=True,
        comment="Autoincrement id number"
    )
    tag = Column(
        String(32),
        nullable=False,
        comment="The tag name"
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        comment="UTC timestamp when the tag record was first created"
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="UTC timestamp of the last update to the tag record"
    )

    @classmethod
    def list(cls, session: Session):
        return session.query(cls).all()