import json

import httpx
import respx
import pytest


class _LiveState:
    def __init__(self, starts: dict[str, int | None]):
        self.starts = starts

    def get_last_live_start(self, uid: str) -> int | None:
        return self.starts.get(uid)

    def set_last_live_start(self, uid: str, live_start: int) -> None:
        self.starts[uid] = live_start


def _live_item(content):
    return {
        "id_str": "1228276701565288466",
        "type": "DYNAMIC_TYPE_LIVE_RCMD",
        "modules": {
            "module_dynamic": {
                "major": None,
                "additional": {
                    "type": "ADDITIONAL_TYPE_LIVE_RCMD",
                    "live_rcmd": {"content": content},
                },
            }
        },
    }


def test_extract_live_url_from_current_major_layout():
    from nonebot_plugin_parser.subscribe import _extract_url_from_item

    item = _live_item(None)
    module_dynamic = item["modules"]["module_dynamic"]
    module_dynamic["additional"] = None
    module_dynamic["major"] = {
        "type": "MAJOR_TYPE_LIVE_RCMD",
        "live": None,
        "live_rcmd": {
            "content": json.dumps(
                {
                    "type": 1,
                    "live_play_info": {
                        "room_id": 242721,
                        "uid": 23396430,
                        "title": "[osu!]DFC被打死了",
                    },
                }
            )
        },
    }

    assert _extract_url_from_item(item) == "https://live.bilibili.com/242721"


def test_extract_live_url_from_json_content():
    from nonebot_plugin_parser.subscribe import _extract_url_from_item

    content = json.dumps({"live_play_info": {"room_id": 123456}})

    assert _extract_url_from_item(_live_item(content)) == "https://live.bilibili.com/123456"


def test_extract_live_url_from_decoded_content():
    from nonebot_plugin_parser.subscribe import _extract_url_from_item

    content = {"live_play_info": {"room_id": "654321"}}

    assert _extract_url_from_item(_live_item(content)) == "https://live.bilibili.com/654321"


def test_invalid_live_content_falls_back_to_dynamic_url():
    from nonebot_plugin_parser.subscribe import _extract_url_from_item

    assert _extract_url_from_item(_live_item("{invalid")) == ("https://t.bilibili.com/1228276701565288466")


def test_live_status_transition_is_announced_once():
    from nonebot_plugin_parser.subscribe import _collect_new_live_sessions

    state = _LiveState({"74152480": 0})
    statuses = {
        "74152480": {
            "live_status": 1,
            "live_time": 1785423611,
            "room_id": 1796293407,
        }
    }

    assert _collect_new_live_sessions(statuses, state) == [("74152480", "1796293407")]
    assert _collect_new_live_sessions(statuses, state) == []


def test_unknown_live_status_is_initialized_without_announcement():
    from nonebot_plugin_parser.subscribe import _collect_new_live_sessions

    state = _LiveState({})
    statuses = {
        "23396430": {
            "live_status": 1,
            "live_time": 1785418703,
            "room_id": 242721,
        }
    }

    assert _collect_new_live_sessions(statuses, state) == []
    assert state.starts["23396430"] == 1785418703


def test_delayed_live_dynamic_is_recognized_as_already_announced():
    from nonebot_plugin_parser.subscribe import _is_announced_live_item

    item = _live_item(
        json.dumps(
            {
                "live_play_info": {
                    "room_id": 1796293407,
                    "live_start_time": 1785423611,
                }
            }
        )
    )
    state = _LiveState({"74152480": 1785423611})

    assert _is_announced_live_item(item, state, "74152480")


@pytest.mark.asyncio
@respx.mock
async def test_live_statuses_are_fetched_in_one_batch():
    from nonebot_plugin_parser.subscribe import (
        _LIVE_STATUS_URL,
        _fetch_live_statuses,
    )

    route = respx.get(_LIVE_STATUS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "message": "success",
                "data": {
                    "74152480": {
                        "live_status": 1,
                        "live_time": 1785423611,
                        "room_id": 1796293407,
                    },
                    "23396430": {"live_status": 0},
                },
            },
        )
    )

    statuses = await _fetch_live_statuses(["74152480", "23396430"])

    assert set(statuses) == {"74152480", "23396430"}
    assert route.call_count == 1
    assert route.calls[0].request.url.params.get_list("uids[]") == [
        "74152480",
        "23396430",
    ]
    assert not route.calls[0].request.headers["user-agent"].startswith("python-httpx")


def test_live_state_is_persisted_with_dynamic_bookmark(tmp_path, monkeypatch):
    import nonebot_plugin_parser.subscribe as subscribe

    path = tmp_path / "subscriptions.json"
    path.write_text(
        json.dumps(
            {
                "subscriptions": [],
                "last_seen": {
                    "74152480": {
                        "last_dynamic_id": "1230876702960254981",
                        "last_live_start": None,
                    }
                },
            }
        )
    )
    monkeypatch.setattr(subscribe, "_SUBS_PATH", path)

    manager = subscribe.SubscriptionManager()
    assert manager.get_last_live_start("74152480") is None

    manager.set_last_live_start("74152480", 1785423611)

    reloaded = subscribe.SubscriptionManager()
    assert reloaded.get_last_seen("74152480") == "1230876702960254981"
    assert reloaded.get_last_live_start("74152480") == 1785423611
