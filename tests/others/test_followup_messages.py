from nonebug import App


async def test_parse_result_exposes_followup_messages(app: App):
    from nonebot_plugin_parser.parsers.data import Platform, ParseResult

    result = ParseResult(
        platform=Platform(name="dummy", display_name="Dummy"),
        followup_messages=["BV1uCzoYEEir"],
    )

    assert result.followup_messages == ["BV1uCzoYEEir"]


async def test_render_messages_appends_followups_after_card(app: App, monkeypatch):
    import nonebot_plugin_parser.renders as renders
    from nonebot_plugin_parser.helper import UniMessage
    from nonebot_plugin_parser.parsers.data import Platform, ParseResult
    from nonebot_plugin_parser.renders.base import BaseRenderer

    class StubRenderer(BaseRenderer):
        async def render_messages(self):
            yield UniMessage("card")

    monkeypatch.setattr(renders, "RENDERER", StubRenderer)
    result = ParseResult(
        platform=Platform(name="dummy", display_name="Dummy"),
        followup_messages=["BV1uCzoYEEir"],
    )

    messages = [message async for message in renders.render_messages(result)]

    assert [message.extract_plain_text() for message in messages] == ["card", "BV1uCzoYEEir"]
