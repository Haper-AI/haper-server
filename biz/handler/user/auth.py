from flask import request
from typing_extensions import Annotated
from pydantic import BaseModel, EmailStr, Field, AfterValidator, ValidationError
from biz.handler.middleware import catch_error
from biz.utils.response import HTTPResponse
from .routes import user_routes


def validate_password(value):
    if not any(char.isalpha() for char in value):
        raise ValueError("Password must contain at least one letter.")
    if not any(char.isdigit() for char in value):
        raise ValueError("Password must contain at least one number.")
    return value


class SignupReq(BaseModel):
    email: EmailStr
    password: Annotated[
        str,
        Field(
            ...,
            min_length=8,
            max_length=64,
            description="Password must contain at least one letter, one number, and be 8-128 characters long.",
        ),
        AfterValidator(validate_password)
    ]


@user_routes.route('/signup', methods=['POST'])
@catch_error
def signup():
    resp = HTTPResponse(request.path)
    req = SignupReq(**request.get_json())
    resp.set_data({
        "email": req.email,
        "password": req.password,
    })
    return resp.return_with_log()


@user_routes.route('/login', methods=['POST'])
def login():
    raise NotImplementedError
