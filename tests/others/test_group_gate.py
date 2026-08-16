from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def gate_plugin(gate, version=2):
    return SimpleNamespace(
        name="group_superuser_gate",
        module_name="group_superuser_gate",
        module=SimpleNamespace(
            GROUP_SUPERUSER_GATE_INTERFACE_VERSION=version,
            event_access_allowed=gate,
        ),
    )


@pytest.fixture(autouse=True)
def group_gate_module():
    from nonebot_plugin_parser import group_gate

    group_gate._group_gate = None
    return group_gate


async def test_auto_mode_uses_loaded_gate_for_groups(group_gate_module):
    from nonebot_plugin_parser.config import GroupGateMode

    gate = AsyncMock(return_value=False)
    with patch.object(group_gate_module, "get_plugin", return_value=gate_plugin(gate)):
        group_gate_module.configure_group_gate(GroupGateMode.auto)

    bot = object()
    event = SimpleNamespace(group_id=200)
    assert not await group_gate_module.gated_event_access_allowed(bot, event)
    gate.assert_awaited_once_with(bot, event)


async def test_auto_mode_allows_when_gate_is_absent(group_gate_module):
    from nonebot_plugin_parser.config import GroupGateMode

    with (
        patch.object(group_gate_module, "get_plugin", return_value=None),
        patch.object(group_gate_module, "get_loaded_plugins", return_value=set()),
    ):
        group_gate_module.configure_group_gate(GroupGateMode.auto)

    assert await group_gate_module.gated_event_access_allowed(object(), SimpleNamespace(group_id=200))


def test_required_mode_rejects_missing_gate(group_gate_module):
    from nonebot_plugin_parser.config import GroupGateMode

    with (
        patch.object(group_gate_module, "get_plugin", return_value=None),
        patch.object(group_gate_module, "get_loaded_plugins", return_value=set()),
        pytest.raises(RuntimeError, match="requires the group_superuser_gate"),
    ):
        group_gate_module.configure_group_gate(GroupGateMode.required)


def test_loaded_incompatible_gate_is_rejected_even_in_auto_mode(group_gate_module):
    from nonebot_plugin_parser.config import GroupGateMode

    with (
        patch.object(group_gate_module, "get_plugin", return_value=gate_plugin(AsyncMock(), version=1)),
        pytest.raises(RuntimeError, match="incompatible interface"),
    ):
        group_gate_module.configure_group_gate(GroupGateMode.auto)


async def test_sensitive_private_messages_use_gate(group_gate_module):
    from nonebot_plugin_parser.config import GroupGateMode

    gate = AsyncMock(return_value=False)
    with patch.object(group_gate_module, "get_plugin", return_value=gate_plugin(gate)):
        group_gate_module.configure_group_gate(GroupGateMode.required)

    bot = object()
    event = SimpleNamespace()
    assert not await group_gate_module.gated_event_access_allowed(bot, event)
    gate.assert_awaited_once_with(bot, event)


async def test_denied_sensitive_message_does_not_reach_parser():
    from nonebot_plugin_parser import matchers

    search_result = object()
    with (
        patch.object(matchers, "gated_event_access_allowed", AsyncMock(return_value=False)),
        patch.object(matchers, "parser_handler", AsyncMock()) as parser_handler,
    ):
        await matchers.sensitive_parser_handler(object(), SimpleNamespace(group_id=200), search_result)

    parser_handler.assert_not_awaited()


async def test_denied_private_bm_does_not_start_download():
    from nonebot_plugin_parser import matchers

    with (
        patch.object(matchers, "private_access_allowed", AsyncMock(return_value=False)),
        patch.object(matchers, "_download_bilibili_audio", AsyncMock()) as download_audio,
    ):
        await matchers.bilibili_audio_handler(object(), SimpleNamespace(), object())

    download_audio.assert_not_awaited()


async def test_regular_group_message_bypasses_gate(group_gate_module):
    from nonebot_plugin_parser.config import GroupGateMode

    gate = AsyncMock(return_value=False)
    with patch.object(group_gate_module, "get_plugin", return_value=gate_plugin(gate)):
        group_gate_module.configure_group_gate(GroupGateMode.required)

    assert await group_gate_module.private_access_allowed(object(), SimpleNamespace(group_id=200))
    gate.assert_not_awaited()


async def test_regular_private_message_uses_gate(group_gate_module):
    from nonebot_plugin_parser.config import GroupGateMode

    gate = AsyncMock(return_value=False)
    with patch.object(group_gate_module, "get_plugin", return_value=gate_plugin(gate)):
        group_gate_module.configure_group_gate(GroupGateMode.required)

    bot = object()
    event = SimpleNamespace()
    assert not await group_gate_module.private_access_allowed(bot, event)
    gate.assert_awaited_once_with(bot, event)


def test_only_twitter_and_youtube_are_sensitive_platforms():
    from nonebot_plugin_parser.parsers import TwitterParser, YouTubeParser, BilibiliParser
    from nonebot_plugin_parser.matchers import _is_sensitive_parser_class

    assert _is_sensitive_parser_class(TwitterParser)
    assert _is_sensitive_parser_class(YouTubeParser)
    assert not _is_sensitive_parser_class(BilibiliParser)
