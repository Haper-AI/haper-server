from datetime import datetime
from typing import List, Any, Optional, TypeVar, Callable, Type, cast
import dateutil.parser


T = TypeVar("T")


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
    return x


def from_datetime(x: Any) -> datetime:
    return dateutil.parser.parse(x)


def from_list(f: Callable[[Any], T], x: Any) -> List[T]:
    assert isinstance(x, list)
    return [f(y) for y in x]


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


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


class MailReportItem:
    action: str
    message_id: int
    receive_at: datetime
    sender: str
    subject: str
    summary: str
    tags: List[str]
    thread_id: int

    def __init__(self, action: str, message_id: int, receive_at: datetime, sender: str, subject: str, summary: str, tags: List[str], thread_id: int) -> None:
        self.action = action
        self.message_id = message_id
        self.receive_at = receive_at
        self.sender = sender
        self.subject = subject
        self.summary = summary
        self.tags = tags
        self.thread_id = thread_id

    @staticmethod
    def from_dict(obj: Any) -> 'MailReportItem':
        assert isinstance(obj, dict)
        action = from_str(obj.get("action"))
        message_id = from_int(obj.get("message_id"))
        receive_at = from_datetime(obj.get("receive_at"))
        sender = from_str(obj.get("sender"))
        subject = from_str(obj.get("subject"))
        summary = from_str(obj.get("summary"))
        tags = from_list(from_str, obj.get("tags"))
        thread_id = from_int(obj.get("thread_id"))
        return MailReportItem(action, message_id, receive_at, sender, subject, summary, tags, thread_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["action"] = from_str(self.action)
        result["message_id"] = from_int(self.message_id)
        result["receive_at"] = self.receive_at.isoformat()
        result["sender"] = from_str(self.sender)
        result["subject"] = from_str(self.subject)
        result["summary"] = from_str(self.summary)
        result["tags"] = from_list(from_str, self.tags)
        result["thread_id"] = from_int(self.thread_id)
        return result


class Gmail:
    essential: List[MailReportItem]
    non_essential: List[MailReportItem]

    def __init__(self, essential: List[MailReportItem], non_essential: List[MailReportItem]) -> None:
        self.essential = essential
        self.non_essential = non_essential

    @staticmethod
    def from_dict(obj: Any) -> 'Gmail':
        assert isinstance(obj, dict)
        essential = from_list(MailReportItem.from_dict, obj.get("essential"))
        non_essential = from_list(MailReportItem.from_dict, obj.get("non_essential"))
        return Gmail(essential, non_essential)

    def to_dict(self) -> dict:
        result: dict = {}
        result["essential"] = from_list(lambda x: to_class(MailReportItem, x), self.essential)
        result["non_essential"] = from_list(lambda x: to_class(MailReportItem, x), self.non_essential)
        return result


class Content:
    content_sources: List[str]
    gmail: Gmail

    def __init__(self, content_sources: List[str], gmail: Gmail) -> None:
        self.content_sources = content_sources
        self.gmail = gmail

    @staticmethod
    def from_dict(obj: Any) -> 'Content':
        assert isinstance(obj, dict)
        content_sources = from_list(from_str, obj.get("content_sources"))
        gmail = Gmail.from_dict(obj.get("gmail"))
        return Content(content_sources, gmail)

    def to_dict(self) -> dict:
        result: dict = {}
        result["content_sources"] = from_list(from_str, self.content_sources)
        result["gmail"] = to_class(Gmail, self.gmail)
        return result


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
    email: str
    name: str

    def __init__(self, email: str, name: str) -> None:
        self.email = email
        self.name = name

    @staticmethod
    def from_dict(obj: Any) -> 'Email':
        assert isinstance(obj, dict)
        email = from_str(obj.get("email"))
        name = from_str(obj.get("name"))
        return Email(email, name)

    def to_dict(self) -> dict:
        result: dict = {}
        result["email"] = from_str(self.email)
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


class Summary:
    annotations: Optional[Annotations]
    email: Optional[Email]
    text: Optional[Text]
    type: str

    def __init__(self, annotations: Optional[Annotations], email: Optional[Email], text: Optional[Text], type: str) -> None:
        self.annotations = annotations
        self.email = email
        self.text = text
        self.type = type

    @staticmethod
    def from_dict(obj: Any) -> 'Summary':
        assert isinstance(obj, dict)
        annotations = from_union([Annotations.from_dict, from_none], obj.get("annotations"))
        email = from_union([Email.from_dict, from_none], obj.get("email"))
        text = from_union([Text.from_dict, from_none], obj.get("text"))
        type = from_str(obj.get("type"))
        return Summary(annotations, email, text, type)

    def to_dict(self) -> dict:
        result: dict = {}
        if self.annotations is not None:
            result["annotations"] = from_union([lambda x: to_class(Annotations, x), from_none], self.annotations)
        if self.email is not None:
            result["email"] = from_union([lambda x: to_class(Email, x), from_none], self.email)
        if self.text is not None:
            result["text"] = from_union([lambda x: to_class(Text, x), from_none], self.text)
        result["type"] = from_str(self.type)
        return result


class Report:
    content: Content
    summary: List[Summary]

    def __init__(self, content: Content, summary: List[Summary]) -> None:
        self.content = content
        self.summary = summary

    @staticmethod
    def from_dict(obj: Any) -> 'Report':
        assert isinstance(obj, dict)
        content = Content.from_dict(obj.get("content"))
        summary = from_list(Summary.from_dict, obj.get("summary"))
        return Report(content, summary)

    def to_dict(self) -> dict:
        result: dict = {}
        result["content"] = to_class(Content, self.content)
        result["summary"] = from_list(lambda x: to_class(Summary, x), self.summary)
        return result


def report_from_dict(s: Any) -> Report:
    return Report.from_dict(s)


def report_to_dict(x: Report) -> Any:
    return to_class(Report, x)
