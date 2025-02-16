import uuid
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    BigInteger,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session
import datetime
from .base import Base


class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'comment': 'Users table, each record corresponding to one unique user'}

    id = Column(
        UUID,
        primary_key=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        comment='Primary key of the users table'
    )
    name = Column(
        String(32),
        comment='The name of the user'
    )
    image = Column(
        Text,
        comment='The portrait URL of the user'
    )
    email = Column(
        String(128),
        nullable=False,
        unique=True,
        comment='The email address of the user, must be unique'
    )
    email_verified = Column(
        Boolean,
        default=False,
        comment='Whether the email of user is verified or not if user registered by email'
    )
    password = Column(
        String(128),
        comment='Hashed password of user'
    )
    created_at = Column(
        TIMESTAMP,
        nullable=False,
        default=datetime.datetime.now(datetime.timezone.utc),
        comment='UTC timestamp when the user was created'
    )

    @classmethod
    def add(cls, session: Session, name: str, email: str, email_verified: bool = False,
            password: Optional[str] = None, image: Optional[str] = None):
        user = cls(name=name, email=email, email_verified=email_verified, password=password, image=image)
        session.add(user)
        session.flush()
        return user

    @classmethod
    def get_by_id(cls, session: Session, user_id: str):
        """
        Fetch a user by their ID from the database.

        :param session: SQLAlchemy session instance
        :param user_id: UUID of the user to fetch
        :return: User object or None if not found
        """
        return session.query(cls).filter(cls.id == user_id).first()

    @classmethod
    def get_by_email(cls, session: Session, email: str):
        """
        Fetch a user by their email from the database.

        :param session: SQLAlchemy session instance
        :param email: UUID of the user to fetch
        :return: User object or None if not found
        """
        return session.query(cls).filter(cls.email == email).first()


class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = (
        {'comment': 'User OAuth accounts, one user can have multiple accounts'}
    )

    user_id = Column(
        UUID,
        ForeignKey('users.id', ondelete="CASCADE"),
        nullable=False,
        comment='The id of users table record'
    )
    provider = Column(
        String(16),
        primary_key=True,
        nullable=False,
        comment='The OAuth provider, like google, discord, etc.'
    )
    provider_account_id = Column(
        Text,
        primary_key=True,
        nullable=False,
        comment='The unique account ID of the user for the provider'
    )
    email = Column(
        String(32),
        comment='The email info returned by the provider, may vary for different providers'
    )
    access_token = Column(
        Text,
        nullable=False,
        comment='The access token returned by the provider'
    )
    refresh_token = Column(
        Text,
        comment='The refresh token returned by the provider, not all providers provide refresh tokens'
    )
    expires_at = Column(
        BigInteger,
        comment='The unix time of when the access token will expire'
    )
    created_at = Column(
        TIMESTAMP,
        nullable=False,
        default=datetime.datetime.now(datetime.timezone.utc),
        comment='UTC timestamp when the account was created'
    )

    @classmethod
    def add(cls, session: Session, user_id: str, provider: str, provider_account_id: str, email: str,
            access_token: str, refresh_token: str, expires_at: int):
        account = cls(
            user_id=user_id,
            provider=provider,
            provider_account_id=provider_account_id,
            email=email,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
        session.add(account)
        session.flush()
        return account

    @classmethod
    def get_by_provider_and_provider_id(cls, session: Session, provider: str, provider_account_id: str):
        return session.query(cls).filter_by(provider=provider, provider_account_id=provider_account_id).first()

    @classmethod
    def get_by_gmail(cls, session: Session, email: str):
        return session.query(cls).filter_by(email=email, provider="google").first()

    @classmethod
    def update_tokens(cls, session: Session, provider: str, provider_account_id: str,
                      access_token: str, refresh_token: Optional[str] = None, expires_at: Optional[int] = None):
        updates = {
            'access_token': access_token,
        }

        if refresh_token:
            updates['refresh_token'] = refresh_token
        if expires_at:
            updates['expires_at'] = expires_at

        session.query(cls).filter_by(provider=provider, provider_account_id=provider_account_id).update(updates)
