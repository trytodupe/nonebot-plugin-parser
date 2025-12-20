import asyncio
from pathlib import Path

from nonebug import App


async def test_media_mode_image_only_downloads_images(app: App, monkeypatch):
    from nonebot_plugin_parser.config import MediaMode, pconfig
    from nonebot_plugin_parser.parsers.base import BaseParser, DOWNLOADER
    from nonebot_plugin_parser.parsers.data import ImageContent, Platform

    class DummyParser(BaseParser):
        platform = Platform(name="dummy", display_name="Dummy")

    parser = DummyParser()

    calls = {"img": 0, "video": 0}

    def fake_download_img(url: str, ext_headers=None):
        calls["img"] += 1
        return asyncio.create_task(asyncio.sleep(0, result=Path("img.jpg")))

    def fake_download_video(url: str, ext_headers=None):
        calls["video"] += 1
        raise AssertionError("video downloads should be disabled in MediaMode.image_only")

    monkeypatch.setattr(DOWNLOADER, "download_img", fake_download_img)
    monkeypatch.setattr(DOWNLOADER, "download_video", fake_download_video)

    old_mode = pconfig.parser_media_mode
    pconfig.parser_media_mode = MediaMode.image_only
    try:
        images = parser.create_image_contents(["https://example.com/1.jpg", "https://example.com/2.jpg"])
        assert len(images) == 2
        assert calls["img"] == 2
        assert all(isinstance(cont, ImageContent) for cont in images)

        video = parser.create_video_content("https://example.com/v.mp4")
        assert video is None

        result = parser.result(contents=[video, *images])
        assert result.contents == images
    finally:
        pconfig.parser_media_mode = old_mode


async def test_media_mode_none_skips_all_media(app: App, monkeypatch):
    from nonebot_plugin_parser.config import MediaMode, pconfig
    from nonebot_plugin_parser.parsers.base import BaseParser, DOWNLOADER
    from nonebot_plugin_parser.parsers.data import Platform

    class DummyParser(BaseParser):
        platform = Platform(name="dummy", display_name="Dummy")

    parser = DummyParser()

    calls = {"img": 0, "video": 0}

    def fake_download_img(url: str, ext_headers=None):
        calls["img"] += 1
        raise AssertionError("image downloads should be disabled in MediaMode.none")

    def fake_download_video(url: str, ext_headers=None):
        calls["video"] += 1
        raise AssertionError("video downloads should be disabled in MediaMode.none")

    monkeypatch.setattr(DOWNLOADER, "download_img", fake_download_img)
    monkeypatch.setattr(DOWNLOADER, "download_video", fake_download_video)

    old_mode = pconfig.parser_media_mode
    pconfig.parser_media_mode = MediaMode.none
    try:
        images = parser.create_image_contents(["https://example.com/1.jpg"])
        assert images == []
        assert calls["img"] == 0

        video = parser.create_video_content("https://example.com/v.mp4")
        assert video is None
        assert calls["video"] == 0

        result = parser.result(contents=[video])
        assert result.contents == []
    finally:
        pconfig.parser_media_mode = old_mode
