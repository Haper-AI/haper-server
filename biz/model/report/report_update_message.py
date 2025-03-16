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


class AccountInfo:
    account_id: str

    def __init__(self, account_id: str) -> None:
        self.account_id = account_id

    @staticmethod
    def from_dict(obj: Any) -> 'AccountInfo':
        assert isinstance(obj, dict)
        account_id = from_str(obj.get("account_id"))
        return AccountInfo(account_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["account_id"] = from_str(self.account_id)
        return result


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
    account_info: AccountInfo
    new_messages: List[GmailNewMessage]

    def __init__(self, account_info: AccountInfo, new_messages: List[GmailNewMessage]) -> None:
        self.account_info = account_info
        self.new_messages = new_messages

    @staticmethod
    def from_dict(obj: Any) -> 'Gmail':
        assert isinstance(obj, dict)
        account_info = AccountInfo.from_dict(obj.get("account_info"))
        new_messages = from_list(GmailNewMessage.from_dict, obj.get("new_messages"))
        return Gmail(account_info, new_messages)

    def to_dict(self) -> dict:
        result: dict = {}
        result["account_info"] = to_class(AccountInfo, self.account_info)
        result["new_messages"] = from_list(lambda x: to_class(GmailNewMessage, x), self.new_messages)
        return result


class Messages:
    gmail: Optional[Gmail]

    def __init__(self, gmail: Optional[Gmail]) -> None:
        self.gmail = gmail

    @staticmethod
    def from_dict(obj: Any) -> 'Messages':
        assert isinstance(obj, dict)
        gmail = from_union([Gmail.from_dict, from_none], obj.get("gmail"))
        return Messages(gmail)

    def to_dict(self) -> dict:
        result: dict = {}
        if self.gmail is not None:
            result["gmail"] = from_union([lambda x: to_class(Gmail, x), from_none], self.gmail)
        return result


class ReportInfo:
    report_id: str

    def __init__(self, report_id: str) -> None:
        self.report_id = report_id

    @staticmethod
    def from_dict(obj: Any) -> 'ReportInfo':
        assert isinstance(obj, dict)
        report_id = from_str(obj.get("report_id"))
        return ReportInfo(report_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["report_id"] = from_str(self.report_id)
        return result


class UserInfo:
    user_id: str

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id

    @staticmethod
    def from_dict(obj: Any) -> 'UserInfo':
        assert isinstance(obj, dict)
        user_id = from_str(obj.get("user_id"))
        return UserInfo(user_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["user_id"] = from_str(self.user_id)
        return result


class ReportUpdateMessage:
    messages: Messages
    report_info: ReportInfo
    user_info: UserInfo

    def __init__(self, messages: Messages, report_info: ReportInfo, user_info: UserInfo) -> None:
        self.messages = messages
        self.report_info = report_info
        self.user_info = user_info

    @staticmethod
    def from_dict(obj: Any) -> 'ReportUpdateMessage':
        assert isinstance(obj, dict)
        messages = Messages.from_dict(obj.get("messages"))
        report_info = ReportInfo.from_dict(obj.get("report_info"))
        user_info = UserInfo.from_dict(obj.get("user_info"))
        return ReportUpdateMessage(messages, report_info, user_info)

    def to_dict(self) -> dict:
        result: dict = {}
        result["messages"] = to_class(Messages, self.messages)
        result["report_info"] = to_class(ReportInfo, self.report_info)
        result["user_info"] = to_class(UserInfo, self.user_info)
        return result


def report_update_message_from_dict(s: Any) -> ReportUpdateMessage:
    return ReportUpdateMessage.from_dict(s)


def report_update_message_to_dict(x: ReportUpdateMessage) -> Any:
    return to_class(ReportUpdateMessage, x)
