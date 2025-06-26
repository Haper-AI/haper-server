from enum import Enum


class ReportFieldName(str, Enum):
    Content = "content"
    MessagesInQueue = "messages_in_queue"
    Summary = "summary"
