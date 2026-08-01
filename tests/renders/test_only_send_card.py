import asyncio

from nonebug import App


async def test_only_send_card_skips_media_messages(app: App, monkeypatch):
    from nonebot_plugin_parser.config import pconfig
    from nonebot_plugin_parser.parsers.data import Platform, ParseResult, ImageContent
    from nonebot_plugin_parser.parsers.task import PathTask
    from nonebot_plugin_parser.renders.default import DefaultRenderer

    monkeypatch.setattr(pconfig, "parser_only_send_card", True)

    async def unexpected_download():
        raise AssertionError("media contents should not be rendered")

    result = ParseResult(
        platform=Platform(name="dummy", display_name="Dummy"),
        title="Card title",
        contents=[ImageContent(PathTask(asyncio.create_task(unexpected_download())))],
    )

    messages = [message async for message in DefaultRenderer(result).render_messages()]

    assert len(messages) == 1
