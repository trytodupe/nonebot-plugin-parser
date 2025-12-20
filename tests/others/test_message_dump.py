import os
import shutil
from pathlib import Path

from nonebug import App


def _summarize_onebot_file(file_value: str) -> str:
    if file_value.startswith("base64://"):
        prefix = file_value[:80]
        return f"base64://... (len={len(file_value)}) prefix={prefix!r}"
    return file_value


def _dump_onebot11_image_segment(seg, out_dir: Path) -> str:
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
    payload = "\n".join(
        [
            f"cq={str(ob)}",
            f"file={_summarize_onebot_file(str(file_value))}",
            f"data={ob.data}",
        ]
    )
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
    return payload


def _apply_test_config_to_pconfig(cfg: dict) -> dict:
    from nonebot_plugin_parser.config import MediaMode, pconfig

    old = {
        "parser_use_base64": pconfig.parser_use_base64,
        "parser_media_mode": pconfig.parser_media_mode,
    }

    plugin_cfg = cfg.get("nonebot_plugin_parser", {})

    if "parser_use_base64" in plugin_cfg:
        pconfig.parser_use_base64 = bool(plugin_cfg["parser_use_base64"])
    if "parser_media_mode" in plugin_cfg:
        pconfig.parser_media_mode = MediaMode(str(plugin_cfg["parser_media_mode"]))

    return old


def _restore_pconfig(old: dict) -> None:
    from nonebot_plugin_parser.config import pconfig

    pconfig.parser_use_base64 = old["parser_use_base64"]
    pconfig.parser_media_mode = old["parser_media_mode"]


async def _parse_url(url: str):
    from nonebot_plugin_parser.parsers import BaseParser

    for cls in BaseParser.get_all_subclass():
        try:
            keyword, searched = cls.search_url(url)
        except Exception:
            continue
        parser = cls()
        return await parser.parse(keyword, searched)
    raise RuntimeError(f"No parser matched url: {url}")


async def test_dump_rendered_card_and_payload(app: App):
    """
    This test doesn't send messages to a real OneBot endpoint.

    Instead it renders the card image and dumps:
    - the image bytes (as `card.png`)
    - the OneBot v11 image segment that would be produced (as `onebot_segment.txt`)

    Output location defaults to pytest's `tmp_path`, but can be overridden via env:
    `PARSER_TEST_DUMP_DIR=/some/path`.
    """
    from nonebot_plugin_parser.renders import get_renderer
    from nonebot_plugin_alconna.uniseg.segment import Image

    # Default dump location: repo-root `temp/out/`.
    dump_root = Path(os.getenv("PARSER_TEST_DUMP_DIR", "")).resolve() if os.getenv("PARSER_TEST_DUMP_DIR") else None
    if dump_root is None:
        dump_root = Path(__file__).resolve().parents[2] / "temp" / "out"
    dump_root.mkdir(parents=True, exist_ok=True)

    # Optional config from repo-root `temp/test_config.toml`
    import tomllib

    cfg_path = Path(__file__).resolve().parents[2] / "temp" / "test_config.toml"
    url = "https://example.com/test"
    cfg: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            cfg = tomllib.load(f)
    test_cfg = cfg.get("test", {})
    url = str(test_cfg.get("url", url))

    # Apply plugin-related config for the parsing/rendering run
    old = _apply_test_config_to_pconfig(cfg)
    try:
        # Parse real URL (network)
        try:
            result = await _parse_url(url)
        except Exception as e:
            import pytest

            pytest.skip(f"parse failed for {url}: {type(e).__name__}: {e}")

        renderer = get_renderer(result.platform.name)

        # Render and dump the "would-send" payload according to config
        from nonebot_plugin_parser.config import pconfig

        seg = await renderer.cache_or_render_image(result)  # type: ignore[attr-defined]
        assert isinstance(seg, Image)

        (dump_root / "url.txt").write_text(f"{url}\n", "utf-8")
        (dump_root / "config.txt").write_text(
            f"parser_use_base64={pconfig.parser_use_base64}\nparser_media_mode={pconfig.parser_media_mode}\n",
            "utf-8",
        )

        if seg.raw:
            (dump_root / "card.png").write_bytes(seg.raw_bytes)
        elif seg.path:
            shutil.copyfile(Path(seg.path), dump_root / "card.png")
        else:
            raise AssertionError("expected Image(raw=...) or Image(path=...)")

        _dump_onebot11_image_segment(seg, dump_root)
    finally:
        _restore_pconfig(old)

    print(f"dumped artifacts to: {dump_root}")
