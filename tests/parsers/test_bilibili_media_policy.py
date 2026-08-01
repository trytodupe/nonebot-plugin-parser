import asyncio
from pathlib import Path

from nonebug import App


async def test_image_only_bilibili_video_keeps_cover_without_starting_video_download(
    app: App,
    monkeypatch,
):
    import nonebot_plugin_parser.parsers.bilibili as bilibili_module
    from nonebot_plugin_parser.config import MediaMode, pconfig
    from nonebot_plugin_parser.parsers.base import downloader
    from nonebot_plugin_parser.parsers.data import Author, ImageContent
    from nonebot_plugin_parser.parsers.bilibili import BilibiliParser

    class FakeVideo:
        def __init__(self, **kwargs):
            pass

        async def get_info(self):
            return {
                "bvid": "BV1uCzoYEEir",
                "title": "Video title",
                "desc": "Description",
                "duration": 120,
                "owner": {"mid": 1, "name": "UP", "face": "https://example.com/avatar.jpg"},
                "stat": {
                    "view": 1,
                    "danmaku": 2,
                    "reply": 3,
                    "favorite": 4,
                    "coin": 5,
                    "share": 6,
                    "like": 7,
                },
                "pubdate": 1_700_000_000,
                "ctime": 1_700_000_000,
                "pic": "https://example.com/cover.jpg",
                "pages": None,
            }

    async def no_credential(self):
        pass

    async def unexpected_extract(*args, **kwargs):
        raise AssertionError("video download must not start in image_only mode")

    def download_img(url: str, ext_headers=None):
        assert url == "https://example.com/cover.jpg"
        return asyncio.create_task(asyncio.sleep(0, result=Path("cover.jpg")))

    monkeypatch.setattr(bilibili_module, "Video", FakeVideo)
    monkeypatch.setattr(BilibiliParser, "_init_credential", no_credential)
    monkeypatch.setattr(BilibiliParser, "extract_download_urls", unexpected_extract)
    monkeypatch.setattr(BilibiliParser, "create_author", lambda *args, **kwargs: Author("UP"))
    monkeypatch.setattr(downloader, "download_img", download_img)
    monkeypatch.setattr(pconfig, "parser_media_mode", MediaMode.image_only)

    result = await BilibiliParser().parse_video(bvid="BV1uCzoYEEir")
    await asyncio.sleep(0)

    assert len(result.contents) == 1
    assert isinstance(result.contents[0], ImageContent)
    assert result.followup_messages == ["BV1uCzoYEEir"]
