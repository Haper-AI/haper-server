from enum import Enum
from typing import Union

from sqlalchemy import Column, ForeignKey, String, func, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from .base import Base


class UserSubscriptionStatus(str, Enum):
    """Enum for user subscription status."""
    Active = "active"
    Trialing = "trialing"
    Paused = "paused"


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = {"comment": "User payment subscription information"}

    user_id = Column(
        UUID,
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        comment="User ID",
    )

    stripe_customer_id = Column(
        String(128),
        comment="Stripe Customer ID",
    )

    stripe_subscription_id = Column(
        String(128),
        nullable=False,
        comment="Stripe Subscription ID",
    )

    subscription_cycle = Column(
        String(16),
        nullable=False,
        comment="Subscription cycle",
    )

    subscription_status = Column(
        String(16),
        nullable=False,
        comment="Subscription status",
    )

    trial_end_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Trial end date",
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the subscription was created",
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the subscription was last updated",
    )

    @classmethod
    def add(cls, session: Session, user_id: Union[UUID, str], stripe_customer_id: str,
            stripe_subscription_id: str, subscription_cycle: str, subscription_status: str,
            trial_end_at: str = None):
        record = cls(
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            subscription_cycle=subscription_cycle,
            subscription_status=subscription_status,
            trial_end_at=trial_end_at,
        )
        session.add(record)
        session.flush()
        return record

    @classmethod
    def update(cls, session: Session, user_id: Union[UUID, str], subscription_status: str = None,
               subscription_cycle: str = None):
        updates = {}
        if subscription_status:
            updates["subscription_status"] = subscription_status
        if subscription_cycle:
            updates["subscription_cycle"] = subscription_cycle
        session.query(cls).filter_by(user_id=user_id).update(updates)

    @classmethod
    def get_by_user_id(cls, session: Session, user_id: Union[UUID, str]):
        return session.query(cls).filter_by(user_id=user_id).first()

    @classmethod
    def get_by_stripe_customer_id(cls, session: Session, stripe_customer_id: str):
        return session.query(cls).filter_by(stripe_customer_id=stripe_customer_id).first()

    @classmethod
    def delete_by_stripe_customer_id(cls, session: Session, stripe_customer_id: str):
        session.query(cls).filter_by(stripe_customer_id=stripe_customer_id).delete()
