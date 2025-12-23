import hashlib
import os
import shutil
from pathlib import Path

from nonebug import App


def _apply_test_config_to_pconfig(cfg: dict) -> dict:
    from nonebot_plugin_parser.config import MediaMode, pconfig
    from nonebot_plugin_parser.constants import RenderType

    old = {
        "parser_use_base64": pconfig.parser_use_base64,
        "parser_media_mode": pconfig.parser_media_mode,
        "parser_render_type": pconfig.parser_render_type,
        "parser_custom_font": pconfig.parser_custom_font,
    }

    plugin_cfg = cfg.get("nonebot_plugin_parser", {})

    if "parser_use_base64" in plugin_cfg:
        pconfig.parser_use_base64 = bool(plugin_cfg["parser_use_base64"])
    if "parser_media_mode" in plugin_cfg:
        pconfig.parser_media_mode = MediaMode(str(plugin_cfg["parser_media_mode"]))
    if "parser_render_type" in plugin_cfg:
        pconfig.parser_render_type = RenderType(str(plugin_cfg["parser_render_type"]))
    if "parser_custom_font" in plugin_cfg:
        pconfig.parser_custom_font = str(plugin_cfg["parser_custom_font"])

    return old


def _restore_pconfig(old: dict) -> None:
    from nonebot_plugin_parser.config import pconfig

    pconfig.parser_use_base64 = old["parser_use_base64"]
    pconfig.parser_media_mode = old["parser_media_mode"]
    pconfig.parser_render_type = old["parser_render_type"]
    pconfig.parser_custom_font = old["parser_custom_font"]


def _ensure_custom_font_available(cfg: dict) -> None:
    """If `parser_custom_font` is set, make sure the file exists under plugin data dir.

    `common` renderer loads font from localstore data dir, not from system fontconfig.
    For local testing convenience, if the font exists in `renders/resources/`, copy it to the data dir.
    """
    from nonebot_plugin_parser.config import pconfig

    plugin_cfg = cfg.get("nonebot_plugin_parser", {})
    font_name = plugin_cfg.get("parser_custom_font")
    if not font_name:
        return

    font_name = str(font_name)
    target = pconfig.data_dir / font_name
    if target.exists():
        return

    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "src" / "nonebot_plugin_parser" / "renders" / "resources" / font_name
    if not src.exists():
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)


def _reload_common_fonts() -> None:
    from nonebot_plugin_parser.renders.common import CommonRenderer

    CommonRenderer._load_fonts()  # pyright: ignore[reportPrivateUsage]


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
    Render cards for one or more URLs and dump PNGs to repo-root `temp/out/`.

    This test doesn't send messages to a real endpoint; it only produces rendered card images.
    """
    from nonebot_plugin_alconna.uniseg.segment import Image

    # Default dump location: repo-root `temp/out/`.
    dump_root = Path(os.getenv("PARSER_TEST_DUMP_DIR", "")).resolve() if os.getenv("PARSER_TEST_DUMP_DIR") else None
    if dump_root is None:
        dump_root = Path(__file__).resolve().parents[2] / "temp" / "out"
    dump_root.mkdir(parents=True, exist_ok=True)

    # Optional config from repo-root `temp/test_config.toml`
    import tomllib

    cfg_path = Path(__file__).resolve().parents[2] / "temp" / "test_config.toml"
    default_url = "https://example.com/test"
    cfg: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            cfg = tomllib.load(f)
    test_cfg = cfg.get("test", {})
    urls_cfg = test_cfg.get("urls")
    if isinstance(urls_cfg, list) and urls_cfg:
        urls = [str(u) for u in urls_cfg]
    elif bool(test_cfg.get("urls_from_test_urls_md", False)):
        urls_file = Path(__file__).parent / "test_urls.md"
        with urls_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        lines = [line.strip() for line in lines if line.strip()]
        urls = [line.removeprefix("-").strip() for line in lines if line.startswith("-")]
        limit = int(test_cfg.get("urls_limit", 3))
        if limit > 0:
            urls = urls[:limit]
    else:
        urls = [str(test_cfg.get("url", default_url))]

    # Apply plugin-related config for the parsing/rendering run
    old = _apply_test_config_to_pconfig(cfg)
    try:
        import importlib

        _ensure_custom_font_available(cfg)
        _reload_common_fonts()

        from nonebot_plugin_parser import renders as renders_module

        # Ensure renderer selection matches updated pconfig (the module computes a global renderer on import).
        importlib.reload(renders_module)

        rendered_files: list[Path] = []
        for index, url in enumerate(urls, start=1):
            # Parse real URL (network)
            try:
                result = await _parse_url(url)
            except Exception as e:
                print(f"skip: parse failed for {url}: {type(e).__name__}: {e}")
                continue

            platform = getattr(result.platform, "name", "unknown") if result.platform else "unknown"
            url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
            out_path = dump_root / f"card_{index:02d}_{platform}_{url_hash}.png"

            try:
                renderer = renders_module.get_renderer(platform)
            except Exception as e:
                print(f"skip: renderer load failed for platform={platform!r}: {type(e).__name__}: {e}")
                continue

            if not hasattr(renderer, "cache_or_render_image"):
                print(f"skip: renderer {type(renderer).__name__} doesn't support image cards (platform={platform!r})")
                continue

            seg = await renderer.cache_or_render_image(result)  # type: ignore[attr-defined]
            if not isinstance(seg, Image):
                print(f"skip: expected Image segment, got {type(seg).__name__} (platform={platform!r})")
                continue

            if seg.raw:
                out_path.write_bytes(seg.raw_bytes)
            elif seg.path:
                shutil.copyfile(Path(seg.path), out_path)
            else:
                print(f"skip: Image segment has no raw/path (platform={platform!r})")
                continue

            rendered_files.append(out_path)
    finally:
        _restore_pconfig(old)
        _reload_common_fonts()

    if rendered_files:
        print(f"dumped {len(rendered_files)} card(s) to: {dump_root}")
    else:
        print(f"no cards dumped (check url(s) and parser_render_type); output dir: {dump_root}")
