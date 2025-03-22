from typing import Optional, Any, TypeVar, Type, cast
from enum import Enum


T = TypeVar("T")
EnumT = TypeVar("EnumT", bound=Enum)


def from_bool(x: Any) -> bool:
    assert isinstance(x, bool)
    return x


def from_none(x: Any) -> Any:
    assert x is None
    return x


def from_union(fs, x):
    for f in fs:
        try:
            return f(x)
        except:
            pass
    assert False


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


def to_enum(c: Type[EnumT], x: Any) -> EnumT:
    assert isinstance(x, c)
    return x.value


class Annotations:
    bold: Optional[bool]

    def __init__(self, bold: Optional[bool]) -> None:
        self.bold = bold

    @staticmethod
    def from_dict(obj: Any) -> 'Annotations':
        assert isinstance(obj, dict)
        bold = from_union([from_bool, from_none], obj.get("bold"))
        return Annotations(bold)

    def to_dict(self) -> dict:
        result: dict = {}
        if self.bold is not None:
            result["bold"] = from_union([from_bool, from_none], self.bold)
        return result


class Email:
    address: str
    name: str

    def __init__(self, address: str, name: str) -> None:
        self.address = address
        self.name = name

    @staticmethod
    def from_dict(obj: Any) -> 'Email':
        assert isinstance(obj, dict)
        address = from_str(obj.get("address"))
        name = from_str(obj.get("name"))
        return Email(address, name)

    def to_dict(self) -> dict:
        result: dict = {}
        result["address"] = from_str(self.address)
        result["name"] = from_str(self.name)
        return result


class Text:
    content: str

    def __init__(self, content: str) -> None:
        self.content = content

    @staticmethod
    def from_dict(obj: Any) -> 'Text':
        assert isinstance(obj, dict)
        content = from_str(obj.get("content"))
        return Text(content)

    def to_dict(self) -> dict:
        result: dict = {}
        result["content"] = from_str(self.content)
        return result


class TypeEnum(Enum):
    EMAIL = "email"
    TEXT = "text"


class RichText:
    annotations: Optional[Annotations]
    email: Optional[Email]
    text: Optional[Text]
    type: TypeEnum

    def __init__(self, annotations: Optional[Annotations], email: Optional[Email], text: Optional[Text], type: TypeEnum) -> None:
        self.annotations = annotations
        self.email = email
        self.text = text
        self.type = type

    @staticmethod
    def from_dict(obj: Any) -> 'RichText':
        assert isinstance(obj, dict)
        annotations = from_union([Annotations.from_dict, from_none], obj.get("annotations"))
        email = from_union([Email.from_dict, from_none], obj.get("email"))
        text = from_union([Text.from_dict, from_none], obj.get("text"))
        type = TypeEnum(obj.get("type"))
        return RichText(annotations, email, text, type)

    def to_dict(self) -> dict:
        result: dict = {}
        if self.annotations is not None:
            result["annotations"] = from_union([lambda x: to_class(Annotations, x), from_none], self.annotations)
        if self.email is not None:
            result["email"] = from_union([lambda x: to_class(Email, x), from_none], self.email)
        if self.text is not None:
            result["text"] = from_union([lambda x: to_class(Text, x), from_none], self.text)
        result["type"] = to_enum(TypeEnum, self.type)
        return result


def rich_text_from_dict(s: Any) -> RichText:
    return RichText.from_dict(s)


def rich_text_to_dict(x: RichText) -> Any:
    return to_class(RichText, x)
