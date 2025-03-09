from datetime import datetime
from typing import List, Any, Optional, Dict, TypeVar, Callable, Type, cast
import dateutil.parser

from biz.model.report.rich_text import RichText

T = TypeVar("T")


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
    return x


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def from_datetime(x: Any) -> datetime:
    return dateutil.parser.parse(x)


def from_list(f: Callable[[Any], T], x: Any) -> List[T]:
    assert isinstance(x, list)
    return [f(y) for y in x]


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


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


def from_bool(x: Any) -> bool:
    assert isinstance(x, bool)
    return x


def from_dict(f: Callable[[Any], T], x: Any) -> Dict[str, T]:
    assert isinstance(x, dict)
    return { k: f(v) for (k, v) in x.items() }


class MailReportItem:
    _id: int
    action: str
    category: str
    message_id: str
    receive_at: datetime
    sender: str
    subject: str
    summary: str
    tags: List[str]
    thread_id: str

    def __init__(self, _id: int, action: str, category: str, message_id: str, receive_at: datetime, sender: str, subject: str, summary: str, tags: List[str], thread_id: str) -> None:
        self._id = _id
        self.action = action
        self.category = category
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
        _id = from_int(obj.get("_id"))
        action = from_str(obj.get("action"))
        category = from_str(obj.get("category"))
        message_id = from_str(obj.get("message_id"))
        receive_at = from_datetime(obj.get("receive_at"))
        sender = from_str(obj.get("sender"))
        subject = from_str(obj.get("subject"))
        summary = from_str(obj.get("summary"))
        tags = from_list(from_str, obj.get("tags"))
        thread_id = from_str(obj.get("thread_id"))
        return MailReportItem(_id, action, category, message_id, receive_at, sender, subject, summary, tags, thread_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["_id"] = from_int(self._id)
        result["action"] = from_str(self.action)
        result["category"] = from_str(self.category)
        result["message_id"] = from_str(self.message_id)
        result["receive_at"] = self.receive_at.isoformat()
        result["sender"] = from_str(self.sender)
        result["subject"] = from_str(self.subject)
        result["summary"] = from_str(self.summary)
        result["tags"] = from_list(from_str, self.tags)
        result["thread_id"] = from_str(self.thread_id)
        return result


class ReportContent:
    content_sources: List[str]
    gmail: Optional[List[MailReportItem]]

    def __init__(self, content_sources: List[str], gmail: Optional[List[MailReportItem]]) -> None:
        self.content_sources = content_sources
        self.gmail = gmail

    @staticmethod
    def from_dict(obj: Any) -> 'ReportContent':
        assert isinstance(obj, dict)
        content_sources = from_list(from_str, obj.get("content_sources"))
        gmail = from_union([lambda x: from_list(MailReportItem.from_dict, x), from_none], obj.get("gmail"))
        return ReportContent(content_sources, gmail)

    def to_dict(self) -> dict:
        result: dict = {}
        result["content_sources"] = from_list(from_str, self.content_sources)
        if self.gmail is not None:
            result["gmail"] = from_union([lambda x: from_list(lambda x: to_class(MailReportItem, x), x), from_none], self.gmail)
        return result


class Report:
    content: ReportContent
    messages_in_queue: Dict[str, int]
    summary: List[RichText]

    def __init__(self, content: ReportContent, messages_in_queue: Dict[str, int], summary: List[RichText]) -> None:
        self.content = content
        self.messages_in_queue = messages_in_queue
        self.summary = summary

    @staticmethod
    def from_dict(obj: Any) -> 'Report':
        assert isinstance(obj, dict)
        content = ReportContent.from_dict(obj.get("content"))
        messages_in_queue = from_dict(from_int, obj.get("messages_in_queue"))
        summary = from_list(RichText.from_dict, obj.get("summary"))
        return Report(content, messages_in_queue, summary)

    def to_dict(self) -> dict:
        result: dict = {}
        result["content"] = to_class(ReportContent, self.content)
        result["messages_in_queue"] = from_dict(from_int, self.messages_in_queue)
        result["summary"] = from_list(lambda x: to_class(RichText, x), self.summary)
        return result


def report_from_dict(s: Any) -> Report:
    return Report.from_dict(s)


def report_to_dict(x: Report) -> Any:
    return to_class(Report, x)
