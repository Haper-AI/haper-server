from typing import Any, List, Optional, TypeVar, Callable, Type, cast


T = TypeVar("T")


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def from_list(f: Callable[[Any], T], x: Any) -> List[T]:
    assert isinstance(x, list)
    return [f(y) for y in x]


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


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


class GmailNewMessage:
    message_id: str
    thread_id: str

    def __init__(self, message_id: str, thread_id: str) -> None:
        self.message_id = message_id
        self.thread_id = thread_id

    @staticmethod
    def from_dict(obj: Any) -> 'GmailNewMessage':
        assert isinstance(obj, dict)
        message_id = from_str(obj.get("message_id"))
        thread_id = from_str(obj.get("thread_id"))
        return GmailNewMessage(message_id, thread_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["message_id"] = from_str(self.message_id)
        result["thread_id"] = from_str(self.thread_id)
        return result


class Gmail:
    account_id: str
    new_messages: List[GmailNewMessage]

    def __init__(self, account_id: str, new_messages: List[GmailNewMessage]) -> None:
        self.account_id = account_id
        self.new_messages = new_messages

    @staticmethod
    def from_dict(obj: Any) -> 'Gmail':
        assert isinstance(obj, dict)
        account_id = from_str(obj.get("account_id"))
        new_messages = from_list(GmailNewMessage.from_dict, obj.get("new_messages"))
        return Gmail(account_id, new_messages)

    def to_dict(self) -> dict:
        result: dict = {}
        result["account_id"] = from_str(self.account_id)
        result["new_messages"] = from_list(lambda x: to_class(GmailNewMessage, x), self.new_messages)
        return result


class Outlook:
    account_id: str
    new_messages: List[str]

    def __init__(self, account_id: str, new_messages: List[str]) -> None:
        self.account_id = account_id
        self.new_messages = new_messages

    @staticmethod
    def from_dict(obj: Any) -> 'Outlook':
        assert isinstance(obj, dict)
        account_id = from_str(obj.get("account_id"))
        new_messages = from_list(from_str, obj.get("new_messages"))
        return Outlook(account_id, new_messages)

    def to_dict(self) -> dict:
        result: dict = {}
        result["account_id"] = from_str(self.account_id)
        result["new_messages"] = from_list(from_str, self.new_messages)
        return result


class Messages:
    gmail: Optional[Gmail]
    outlook: Optional[Outlook]

    def __init__(self, gmail: Optional[Gmail], outlook: Optional[Outlook]) -> None:
        self.gmail = gmail
        self.outlook = outlook

    @staticmethod
    def from_dict(obj: Any) -> 'Messages':
        assert isinstance(obj, dict)
        gmail = from_union([Gmail.from_dict, from_none], obj.get("gmail"))
        outlook = from_union([Outlook.from_dict, from_none], obj.get("outlook"))
        return Messages(gmail, outlook)

    def to_dict(self) -> dict:
        result: dict = {}
        if self.gmail is not None:
            result["gmail"] = from_union([lambda x: to_class(Gmail, x), from_none], self.gmail)
        if self.outlook is not None:
            result["outlook"] = from_union([lambda x: to_class(Outlook, x), from_none], self.outlook)
        return result


class ReportUpdateMessage:
    messages: Messages
    report_id: str
    user_id: str

    def __init__(self, messages: Messages, report_id: str, user_id: str) -> None:
        self.messages = messages
        self.report_id = report_id
        self.user_id = user_id

    @staticmethod
    def from_dict(obj: Any) -> 'ReportUpdateMessage':
        assert isinstance(obj, dict)
        messages = Messages.from_dict(obj.get("messages"))
        report_id = from_str(obj.get("report_id"))
        user_id = from_str(obj.get("user_id"))
        return ReportUpdateMessage(messages, report_id, user_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["messages"] = to_class(Messages, self.messages)
        result["report_id"] = from_str(self.report_id)
        result["user_id"] = from_str(self.user_id)
        return result


def report_update_message_from_dict(s: Any) -> ReportUpdateMessage:
    return ReportUpdateMessage.from_dict(s)


def report_update_message_to_dict(x: ReportUpdateMessage) -> Any:
    return to_class(ReportUpdateMessage, x)
