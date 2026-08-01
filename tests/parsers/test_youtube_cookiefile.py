from pathlib import Path

from nonebug import App


async def test_youtube_uses_cookiefile_from_data_dir(
    app: App,
    monkeypatch,
    tmp_path: Path,
):
    import nonebot_plugin_parser.config as config_module
    from nonebot_plugin_parser.config import pconfig
    from nonebot_plugin_parser.parsers.youtube import YouTubeParser

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    data_dir.mkdir()
    config_dir.mkdir()
    cookiefile = data_dir / "ytb_cookies.txt"
    cookiefile.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

    monkeypatch.setattr(config_module, "_data_dir", data_dir)
    monkeypatch.setattr(config_module, "_config_dir", config_dir)
    monkeypatch.setattr(pconfig, "parser_ytb_ck", None)

    assert YouTubeParser().cookies_file == cookiefile
