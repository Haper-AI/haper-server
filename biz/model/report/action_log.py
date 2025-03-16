from typing import Any, TypeVar, Type, cast


T = TypeVar("T")


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
    return x


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


class ActionLog:
    at: int
    id: int
    message: str

    def __init__(self, at: int, id: int, message: str) -> None:
        self.at = at
        self.id = id
        self.message = message

    @staticmethod
    def from_dict(obj: Any) -> 'ActionLog':
        assert isinstance(obj, dict)
        at = from_int(obj.get("at"))
        id = from_int(obj.get("id"))
        message = from_str(obj.get("message"))
        return ActionLog(at, id, message)

    def to_dict(self) -> dict:
        result: dict = {}
        result["at"] = from_int(self.at)
        result["id"] = from_int(self.id)
        result["message"] = from_str(self.message)
        return result


def action_log_from_dict(s: Any) -> ActionLog:
    return ActionLog.from_dict(s)


def action_log_to_dict(x: ActionLog) -> Any:
    return to_class(ActionLog, x)
