from typing import Any, TypeVar, Type, cast


T = TypeVar("T")


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


class ReportBatchActionMessage:
    report_id: str
    run_id: str

    def __init__(self, report_id: str, run_id: str) -> None:
        self.report_id = report_id
        self.run_id = run_id

    @staticmethod
    def from_dict(obj: Any) -> 'ReportBatchActionMessage':
        assert isinstance(obj, dict)
        report_id = from_str(obj.get("report_id"))
        run_id = from_str(obj.get("run_id"))
        return ReportBatchActionMessage(report_id, run_id)

    def to_dict(self) -> dict:
        result: dict = {}
        result["report_id"] = from_str(self.report_id)
        result["run_id"] = from_str(self.run_id)
        return result


def report_batch_action_message_from_dict(s: Any) -> ReportBatchActionMessage:
    return ReportBatchActionMessage.from_dict(s)


def report_batch_action_message_to_dict(x: ReportBatchActionMessage) -> Any:
    return to_class(ReportBatchActionMessage, x)
