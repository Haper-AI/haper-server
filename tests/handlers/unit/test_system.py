from biz.dal.system_preset import PresetMessageTag
from biz.service.db import get_session
from .conftest import *

class TestSystem:
    def test_success(self, client):
        with get_session(write=True) as session:
            tag = PresetMessageTag(tag="Newsletter")
            session.add(tag)
        response = client.get("/api/v1/system/message_tags")
        assert response.status_code == 200
        assert len(response.get_json()['data']['message_tags']) != 0
