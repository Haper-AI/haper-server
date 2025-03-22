from enum import Enum
from typing import Any, Optional, TypeVar, Type, cast

from biz.model.report.report_batch_action_message import ReportBatchActionMessage
from biz.model.report.report_update_message import ReportUpdateMessage

T = TypeVar("T")
EnumT = TypeVar("EnumT", bound=Enum)


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


def to_enum(c: Type[EnumT], x: Any) -> EnumT:
    assert isinstance(x, c)
    return x.value


class ActionType(Enum):
    REPORT_BATCH_ACTION = "report_batch_action"
    REPORT_UPDATE = "report_update"


class SqsMessage:
    action_type: ActionType
    report_batch_action_message: Optional[ReportBatchActionMessage]
    report_update_message: Optional[ReportUpdateMessage]

    def __init__(self, action_type: ActionType, report_batch_action_message: Optional[ReportBatchActionMessage],
                 report_update_message: Optional[ReportUpdateMessage]) -> None:
        self.action_type = action_type
        self.report_batch_action_message = report_batch_action_message
        self.report_update_message = report_update_message

    @staticmethod
    def from_dict(obj: Any) -> 'SqsMessage':
        assert isinstance(obj, dict)
        action_type = ActionType(obj.get("action_type"))
        report_batch_action_message = from_union([ReportBatchActionMessage.from_dict, from_none],
                                                 obj.get("report_batch_action_message"))
        report_update_message = from_union([ReportUpdateMessage.from_dict, from_none], obj.get("report_update_message"))
        return SqsMessage(action_type, report_batch_action_message, report_update_message)

    def to_dict(self) -> dict:
        result: dict = {}
        result["action_type"] = to_enum(ActionType, self.action_type)
        if self.report_batch_action_message is not None:
            result["report_batch_action_message"] = from_union(
                [lambda x: to_class(ReportBatchActionMessage, x), from_none], self.report_batch_action_message)
        if self.report_update_message is not None:
            result["report_update_message"] = from_union([lambda x: to_class(ReportUpdateMessage, x), from_none],
                                                         self.report_update_message)
        return result


def sqs_message_from_dict(s: Any) -> SqsMessage:
    return SqsMessage.from_dict(s)


def sqs_message_to_dict(x: SqsMessage) -> Any:
    return to_class(SqsMessage, x)
