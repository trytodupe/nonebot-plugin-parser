import asyncio
from pathlib import Path

import pytest
from nonebug import App


@pytest.mark.parametrize("room_id", [21273775, 123])
async def test_live_uses_room_get_info_when_get_info_by_room_is_blocked(app: App, monkeypatch, room_id):
    from bilibili_api.exceptions import ResponseCodeException
    from bilibili_api.utils.network import Api

    from nonebot_plugin_parser.parsers.base import downloader
    from nonebot_plugin_parser.parsers.data import Author
    from nonebot_plugin_parser.parsers.bilibili import BilibiliParser

    calls = []

    async def request(api, **kwargs):
        calls.append((api.url, api.params.copy()))
        if api.url.endswith("/getInfoByRoom"):
            raise ResponseCodeException(-352, "-352", {"code": -352})
        if api.url == "https://api.live.bilibili.com/room/v1/Room/get_info":
            assert api.params["room_id"] == room_id
            return {
                "room_id": 21273775,
                "uid": 350960704,
                "title": "Test stream",
                "user_cover": "https://example.com/cover.jpg",
                "keyframe": "https://example.com/keyframe.jpg",
                "tags": "osu",
                "area_name": "音游",
                "parent_area_name": "单机游戏",
            }
        if api.url == "https://api.bilibili.com/x/web-interface/card":
            assert api.params["mid"] == 350960704
            return {"card": {"name": "Streamer", "face": "https://example.com/avatar.jpg"}}
        raise AssertionError(f"Unexpected API: {api.url}")

    async def no_credential(self):
        pass

    def download_img(url, **kwargs):
        return asyncio.create_task(asyncio.sleep(0, result=Path(url.rsplit("/", 1)[-1])))

    monkeypatch.setattr(Api, "request", request)
    monkeypatch.setattr(BilibiliParser, "_init_credential", no_credential)
    monkeypatch.setattr(BilibiliParser, "create_author", lambda self, name, avatar: Author(name))
    monkeypatch.setattr(downloader, "download_img", download_img)

    parser = BilibiliParser()
    keyword, searched = parser.search_url(f"https://live.bilibili.com/{room_id}")
    result = await parser.parse(keyword, searched)
    await asyncio.sleep(0)

    assert result.title == "直播 - Test stream"
    assert result.author.name == "Streamer"
    assert result.text == "分区: 音游 | 单机游戏\n标签: osu"
    assert len(result.contents) == 2
    assert len(calls) == 2
