from pathlib import Path

from nonebug import App


async def test_image_use_base64_sends_raw(app: App, tmp_path: Path):
    from nonebot_plugin_parser.config import pconfig
    from nonebot_plugin_parser.helper import UniHelper

    img_path = tmp_path / "test.png"
    img_bytes = b"\x89PNG\r\n\x1a\nfake"
    img_path.write_bytes(img_bytes)

    old = pconfig.parser_image_use_base64
    pconfig.parser_image_use_base64 = True
    try:
        seg = UniHelper.img_seg(img_path=img_path)
        assert seg.raw == img_bytes
        assert seg.path is None
    finally:
        pconfig.parser_image_use_base64 = old


async def test_image_use_base64_false_uses_path(app: App, tmp_path: Path):
    from nonebot_plugin_parser.config import pconfig
    from nonebot_plugin_parser.helper import UniHelper

    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    old = pconfig.parser_image_use_base64
    pconfig.parser_image_use_base64 = False
    try:
        seg = UniHelper.img_seg(img_path=img_path)
        assert seg.path is not None
        assert Path(seg.path) == img_path
    finally:
        pconfig.parser_image_use_base64 = old

