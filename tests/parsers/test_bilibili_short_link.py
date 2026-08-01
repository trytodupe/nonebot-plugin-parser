from unittest.mock import AsyncMock

from nonebug import App


async def test_b23_short_link_redirects_to_video_parser(app: App, monkeypatch):
    from nonebot_plugin_parser.parsers.bilibili import BilibiliParser

    parser = BilibiliParser()
    expected = parser.result(url="https://bilibili.com/BV1pGuuzBEFy")
    redirect = AsyncMock(return_value="https://www.bilibili.com/video/BV1pGuuzBEFy")
    parse_video = AsyncMock(return_value=expected)
    monkeypatch.setattr(parser, "get_redirect_url", redirect)
    monkeypatch.setattr(parser, "parse_video", parse_video)

    keyword, searched = parser.search_url("https://b23.tv/S9DodEM")
    result = await parser.parse(keyword, searched)

    assert result is expected
    redirect.assert_awaited_once_with(
        "https://b23.tv/S9DodEM",
        headers=parser.headers,
    )
    parse_video.assert_awaited_once_with(bvid="BV1pGuuzBEFy", page_num=1)
