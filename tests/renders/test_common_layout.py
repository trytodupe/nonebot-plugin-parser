import pytest


@pytest.mark.asyncio
async def test_common_text_before_images_for_twitter_and_bilibili(tmp_path):
    from PIL import Image as PILImage

    from nonebot_plugin_parser.parsers.data import Author, ImageContent, ParseResult, Platform
    from nonebot_plugin_parser.renders.common import CommonRenderer, ImageGridSectionData, TextSectionData

    img_path = tmp_path / "img.jpg"
    PILImage.new("RGB", (64, 64), (255, 0, 0)).save(img_path)

    renderer = CommonRenderer()
    content_width = renderer.DEFAULT_CARD_WIDTH - 2 * renderer.PADDING

    async def assert_text_before_images(platform_name: str, display_name: str):
        result = ParseResult(
            platform=Platform(name=platform_name, display_name=display_name),
            author=Author(name="Tester"),
            text="hello world",
            contents=[ImageContent(img_path)],
        )

        sections = await renderer._calculate_sections(result, content_width)  # pyright: ignore[reportPrivateUsage]
        kinds = [type(s) for s in sections]
        assert TextSectionData in kinds, "expected text section"
        assert ImageGridSectionData in kinds, "expected image grid section"
        assert kinds.index(TextSectionData) < kinds.index(ImageGridSectionData), "text should be before images"

    await assert_text_before_images("twitter", "小蓝鸟")
    await assert_text_before_images("bilibili", "哔哩哔哩")


def test_common_wrap_text_replaces_missing_glyphs():
    from nonebot_plugin_parser.renders.common import CommonRenderer

    renderer = CommonRenderer()
    font = renderer.fontset.text
    lines = renderer._wrap_text("滪旸", 9999, font)  # pyright: ignore[reportPrivateUsage]

    combined = "".join(lines)
    assert len(combined) == 2
    assert combined.strip() != ""

