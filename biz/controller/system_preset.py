from biz.dal.system_preset import PresetMessageTag
from biz.service.db import get_session


def list_message_tags():
    with get_session(write=False) as session:
        tags = PresetMessageTag.list(session)

    result = []
    for t in tags:
        result.append(t.tag)
    return result