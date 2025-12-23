import pytest

class _ExplodingContent:
    async def get_path(self):
        raise AssertionError("render_contents should not be called when parser_card_only=true")


@pytest.mark.asyncio
async def test_card_only_skips_contents(app):
    from nonebot_plugin_parser.renders.base import ImageRenderer
    from nonebot_plugin_parser.parsers.data import ParseResult, Platform
    from nonebot_plugin_parser.config import pconfig

    class _TestRenderer(ImageRenderer):
        async def render_image(self, result: ParseResult) -> bytes:
            # Minimal PNG bytes (header + IEND)
            return (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x00IEND\xaeB`\x82"
            )

    renderer = _TestRenderer()
    result = ParseResult(platform=Platform(name="dummy", display_name="Dummy"), contents=[_ExplodingContent()])  # type: ignore[arg-type]

    old = pconfig.parser_card_only
    pconfig.parser_card_only = True
    try:
        messages = [m async for m in renderer.render_messages(result)]
        assert len(messages) == 1
    finally:
        pconfig.parser_card_only = old


@pytest.mark.asyncio
async def test_card_only_false_calls_contents(app):
    from nonebot_plugin_parser.renders.base import ImageRenderer
    from nonebot_plugin_parser.parsers.data import ParseResult, Platform
    from nonebot_plugin_parser.config import pconfig

    class _TestRenderer(ImageRenderer):
        async def render_image(self, result: ParseResult) -> bytes:
            # Minimal PNG bytes (header + IEND)
            return (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x00IEND\xaeB`\x82"
            )

    renderer = _TestRenderer()
    result = ParseResult(platform=Platform(name="dummy", display_name="Dummy"), contents=[_ExplodingContent()])  # type: ignore[arg-type]

    old = pconfig.parser_card_only
    pconfig.parser_card_only = False
    try:
        with pytest.raises(AssertionError):
            _ = [m async for m in renderer.render_messages(result)]
    finally:
        pconfig.parser_card_only = old


@pytest.mark.asyncio
async def test_only_send_card_skips_contents_for_all_renderers(app):
    from nonebot_plugin_parser.config import pconfig
    from nonebot_plugin_parser.parsers.data import ParseResult, Platform
    from nonebot_plugin_parser.renders.base import ImageRenderer
    from nonebot_plugin_parser.renders.default import DefaultRenderer

    class _TestImageRenderer(ImageRenderer):
        async def render_image(self, result: ParseResult) -> bytes:
            return (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x00IEND\xaeB`\x82"
            )

    img_renderer = _TestImageRenderer()
    default_renderer = DefaultRenderer()
    result = ParseResult(platform=Platform(name="dummy", display_name="Dummy"), contents=[_ExplodingContent()])  # type: ignore[arg-type]

    old_card_only = pconfig.parser_card_only
    old_only_send_card = pconfig.parser_only_send_card
    pconfig.parser_card_only = False
    pconfig.parser_only_send_card = True
    try:
        # Image renderer: only the card message should be produced
        msgs = [m async for m in img_renderer.render_messages(result)]
        assert len(msgs) == 1

        # Default renderer: should produce only the summary message and skip media contents
        msgs2 = [m async for m in default_renderer.render_messages(result)]
        assert len(msgs2) == 1
    finally:
        pconfig.parser_card_only = old_card_only
        pconfig.parser_only_send_card = old_only_send_card
