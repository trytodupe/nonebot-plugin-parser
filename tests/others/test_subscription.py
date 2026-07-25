import json


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
