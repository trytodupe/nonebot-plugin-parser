def test_detect_youtube_cookiefile_prefers_data_dir(monkeypatch, tmp_path):
    import nonebot_plugin_parser.config as cfg

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    data_dir.mkdir()
    config_dir.mkdir()

    monkeypatch.setattr(cfg, "_data_dir", data_dir)
    monkeypatch.setattr(cfg, "_config_dir", config_dir)

    cookiefile = data_dir / "ytb_cookies.txt"
    cookiefile.write_text(
        "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tabc\n",
        encoding="utf-8",
    )

    from nonebot_plugin_parser.parsers.youtube import detect_youtube_cookiefile

    assert detect_youtube_cookiefile() == cookiefile


def test_detect_youtube_cookiefile_fallback_to_config_dir(monkeypatch, tmp_path):
    import nonebot_plugin_parser.config as cfg

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    data_dir.mkdir()
    config_dir.mkdir()

    monkeypatch.setattr(cfg, "_data_dir", data_dir)
    monkeypatch.setattr(cfg, "_config_dir", config_dir)

    cookiefile = config_dir / "ytb_cookies.txt"
    cookiefile.write_text(
        "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSESSDATA\tabc\n",
        encoding="utf-8",
    )

    from nonebot_plugin_parser.parsers.youtube import detect_youtube_cookiefile

    assert detect_youtube_cookiefile() == cookiefile

