import asyncio
from pathlib import Path

from nonebug import App


async def test_image_only_keeps_images_and_cancels_video_download(
    app: App,
    monkeypatch,
):
    from nonebot_plugin_parser.config import MediaMode, pconfig
    from nonebot_plugin_parser.parsers.base import BaseParser, downloader
    from nonebot_plugin_parser.parsers.data import Platform

    class DummyParser(BaseParser):
        platform = Platform(name="dummy", display_name="Dummy")

    image_downloads = 0
    video_started = False

    async def download_video() -> Path:
        nonlocal video_started
        video_started = True
        return Path("video.mp4")

    def download_img(url: str, ext_headers=None):
        nonlocal image_downloads
        image_downloads += 1
        return asyncio.create_task(asyncio.sleep(0, result=Path("image.jpg")))

    monkeypatch.setattr(downloader, "download_img", download_img)
    monkeypatch.setattr(pconfig, "parser_media_mode", MediaMode.image_only)

    parser = DummyParser()
    video_task = asyncio.create_task(download_video())
    assert parser.create_video(video_task, "https://example.com/cover.jpg") is None
    images = parser.create_images(["https://example.com/image.jpg"])
    await asyncio.sleep(0)

    assert video_task.cancelled()
    assert not video_started
    assert len(images) == 1
    assert image_downloads == 1


async def test_none_skips_image_downloads(app: App, monkeypatch):
    from nonebot_plugin_parser.config import MediaMode, pconfig
    from nonebot_plugin_parser.parsers.base import BaseParser, downloader
    from nonebot_plugin_parser.parsers.data import Platform

    class DummyParser(BaseParser):
        platform = Platform(name="dummy", display_name="Dummy")

    def unexpected_download(*args, **kwargs):
        raise AssertionError("media download should not start in MediaMode.none")

    monkeypatch.setattr(downloader, "download_img", unexpected_download)
    monkeypatch.setattr(pconfig, "parser_media_mode", MediaMode.none)

    parser = DummyParser()
    assert parser.create_images(["https://example.com/image.jpg"]) == []
    assert parser.create_image("https://example.com/image.jpg") is None
