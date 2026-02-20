import sys
import types

# Avoid importing optional cairo-backed emosvg in minimal test env.
sys.modules.setdefault("emosvg", types.ModuleType("emosvg"))


def test_extract_bilibili_bvid():
    from nonebot_plugin_parser.constants import PlatformEnum
    from nonebot_plugin_parser.matchers import _extract_bilibili_bvid
    from nonebot_plugin_parser.parsers.data import ParseResult, Platform

    result = ParseResult(
        platform=Platform(name=PlatformEnum.BILIBILI, display_name="bilibili"),
        extra={"bvid": "BV1uCzoYEEir"},
    )
    assert _extract_bilibili_bvid(result) == "BV1uCzoYEEir"


def test_extract_bilibili_bvid_reject_invalid_value():
    from nonebot_plugin_parser.constants import PlatformEnum
    from nonebot_plugin_parser.matchers import _extract_bilibili_bvid
    from nonebot_plugin_parser.parsers.data import ParseResult, Platform

    result = ParseResult(
        platform=Platform(name=PlatformEnum.BILIBILI, display_name="bilibili"),
        extra={"bvid": 123},
    )
    assert _extract_bilibili_bvid(result) is None


def test_extract_bilibili_bvid_reject_non_bilibili():
    from nonebot_plugin_parser.constants import PlatformEnum
    from nonebot_plugin_parser.matchers import _extract_bilibili_bvid
    from nonebot_plugin_parser.parsers.data import ParseResult, Platform

    result = ParseResult(
        platform=Platform(name=PlatformEnum.TWITTER, display_name="twitter"),
        extra={"bvid": "BV1uCzoYEEir"},
    )
    assert _extract_bilibili_bvid(result) is None
