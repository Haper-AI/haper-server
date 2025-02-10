from flask import request
from pydantic import BaseModel, EmailStr, PositiveInt, Field, AfterValidator, model_validator
from typing import Optional
from typing_extensions import Annotated
from biz.handler.middleware import catch_error, gen_jwt_auth
from biz.utils.response import HTTPResponse
from biz.controller.user import (
    signup_user_by_credential,
    signup_user_by_oauth,
    login_user_with_credential,
    login_user_by_oauth,
)
from .routes import user_routes

CREDENTIALS_PROVIDER = 'credentials'


class SignupReq(BaseModel):
    """Signup request"""
    provider: Annotated[
        str,
        Field(..., description="Provider field cannot be empty.")
    ]
    email: EmailStr
    password: Optional[str] = None
    provider_account_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[PositiveInt] = None
    name: Optional[str] = None
    image: Optional[str] = None

    @model_validator(mode='after')
    def validate_req(self):
        if self.provider == CREDENTIALS_PROVIDER:
            # validate password
            if not self.password:
                raise ValueError("Password cannot be empty.")
            if len(self.password) < 8:
                raise ValueError("Password must be at least 8 characters long.")
            if len(self.password) > 32:
                raise ValueError("Password must be at most 32 characters long.")
            if not any(char.isalpha() for char in self.password):
                raise ValueError("Password must contain at least one letter.")
            if not any(char.isdigit() for char in self.password):
                raise ValueError("Password must contain at least one number.")
        else:  # else user sign up with oauth
            # require provider_account_id for oauth
            if not self.provider_account_id:
                raise ValueError("Provider account id cannot be empty.")
            # require access_token for oauth
            if not self.access_token:
                raise ValueError("Access token cannot be empty.")
        return self


@user_routes.route('/signup', methods=['POST'])
@catch_error
def signup():
    resp = HTTPResponse(request.method, request.path)
    req = SignupReq(**request.get_json())
    if req.provider == CREDENTIALS_PROVIDER:
        user = signup_user_by_credential(str(req.email), req.password)
    else:
        user, _ = signup_user_by_oauth(req.provider, req.provider_account_id, str(req.email),
                                       req.access_token, req.refresh_token, req.expires_at,
                                       req.name, req.image)

    resp.set_data({
        'user': {
            'id': user.id,
            'name': user.name,
            'image': user.image,
            'email': user.email,
            'email_verified': user.email_verified,
            'created_at': user.created_at,
        }
    })
    resp.set_jwt_auth_cookie(gen_jwt_auth(str(user.id)))
    return resp.return_with_log()


class LoginReq(BaseModel):
    """Login request"""
    provider: Annotated[
        str,
        Field(..., description="Provider field cannot be empty.")
    ]
    email: EmailStr
    password: Optional[str] = None
    provider_account_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[PositiveInt] = None

    @model_validator(mode='after')
    def validate_req(self):
        if self.provider == CREDENTIALS_PROVIDER:
            # validate password
            if not self.password:
                raise ValueError("Password cannot be empty.")
        else:  # else user sign up with oauth
            # require provider_account_id for oauth
            if not self.provider_account_id:
                raise ValueError("Provider account id cannot be empty.")
            # require access_token for oauth
            if not self.access_token:
                raise ValueError("Access token cannot be empty.")
        return self


@user_routes.route('/login', methods=['POST'])
@catch_error
def login():
    resp = HTTPResponse(request.method, request.path)
    req = LoginReq(**request.get_json())
    if req.provider == CREDENTIALS_PROVIDER:
        user = login_user_with_credential(str(req.email), req.password)
    else:
        user = login_user_by_oauth(
            req.provider, req.provider_account_id,
            req.access_token, req.refresh_token, req.expires_at
        )

    resp.set_data({
        'user': {
            'id': user.id,
            'name': user.name,
            'image': user.image,
            'email': user.email,
            'email_verified': user.email_verified,
            'created_at': user.created_at,
        }
    })
    resp.set_jwt_auth_cookie(gen_jwt_auth(str(user.id)))
    return resp.return_with_log()
