import os
import time
import shutil
from pathlib import Path

from nonebug import App


def _summarize_onebot_file(file_value: str) -> str:
    if file_value.startswith("base64://"):
        prefix = file_value[:80]
        return f"base64://... (len={len(file_value)}) prefix={prefix!r}"
    return file_value


def _dump_onebot11_image_segment(seg, out_dir: Path) -> None:
    from nonebot.adapters.onebot.v11.message import MessageSegment

    if seg.raw:
        ob = MessageSegment.image(seg.raw_bytes)
    elif seg.path:
        ob = MessageSegment.image(Path(seg.path))
    elif seg.url:
        ob = MessageSegment.image(seg.url)
    else:
        raise AssertionError("Image segment has no raw/path/url")

    file_value = ob.data.get("file", "")
    (out_dir / "onebot_segment.txt").write_text(
        "\n".join(
            [
                f"cq={str(ob)}",
                f"file={_summarize_onebot_file(str(file_value))}",
                f"data={ob.data}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


async def test_dump_rendered_card_and_payload(app: App, tmp_path: Path):
    """
    This test doesn't send messages to a real OneBot endpoint.

    Instead it renders the card image and dumps:
    - the image bytes (as `card.png`)
    - the OneBot v11 image segment that would be produced (as `onebot_segment.txt`)

    Output location defaults to pytest's `tmp_path`, but can be overridden via env:
    `PARSER_TEST_DUMP_DIR=/some/path`.
    """
    from nonebot_plugin_parser.config import pconfig
    from nonebot_plugin_parser.renders import get_renderer
    from nonebot_plugin_parser.parsers.data import Author, ParseResult, Platform
    from nonebot_plugin_alconna.uniseg.segment import Image

    dump_root = Path(os.getenv("PARSER_TEST_DUMP_DIR", str(tmp_path))).resolve()
    dump_root.mkdir(parents=True, exist_ok=True)

    platform = Platform(name="twitter", display_name="Twitter")
    result = ParseResult(
        platform=platform,
        author=Author(name="tester"),
        title="test title",
        text="test text",
        timestamp=int(time.time()),
        url="https://example.com/test",
    )
    renderer = get_renderer(platform.name)

    old_image_b64 = pconfig.parser_image_use_base64
    old_all_b64 = pconfig.parser_use_base64
    try:
        # Case 1: base64 image (recommended for split containers)
        pconfig.parser_image_use_base64 = True
        pconfig.parser_use_base64 = False
        seg = await renderer.cache_or_render_image(result)  # type: ignore[attr-defined]
        assert isinstance(seg, Image)
        base64_dir = dump_root / "base64"
        base64_dir.mkdir(parents=True, exist_ok=True)
        (base64_dir / "config.txt").write_text("parser_image_use_base64=true\nparser_use_base64=false\n", "utf-8")
        assert seg.raw, "expected Image(raw=...) when parser_image_use_base64=true"
        (base64_dir / "card.png").write_bytes(seg.raw_bytes)
        _dump_onebot11_image_segment(seg, base64_dir)

        # Case 2: path image (single-container / shared volume)
        pconfig.parser_image_use_base64 = False
        pconfig.parser_use_base64 = False
        seg2 = await renderer.cache_or_render_image(result)  # type: ignore[attr-defined]
        assert isinstance(seg2, Image)
        path_dir = dump_root / "path"
        path_dir.mkdir(parents=True, exist_ok=True)
        (path_dir / "config.txt").write_text("parser_image_use_base64=false\nparser_use_base64=false\n", "utf-8")
        assert seg2.path, "expected Image(path=...) when base64 is disabled"
        shutil.copyfile(Path(seg2.path), path_dir / "card.png")
        _dump_onebot11_image_segment(seg2, path_dir)
    finally:
        pconfig.parser_image_use_base64 = old_image_b64
        pconfig.parser_use_base64 = old_all_b64

    print(f"dumped artifacts to: {dump_root}")

