from pathlib import Path
from typing import Any

from typing_extensions import override

from nonebot import require

require("nonebot_plugin_htmlkit")
from nonebot_plugin_htmlkit import template_to_pic

from .base import ImageRenderer, ParseResult


async def _resolve_result(result: ParseResult) -> dict[str, Any]:
    data: dict[str, Any] = {
        "title": result.title,
        "text": result.text,
        "formatted_datetime": result.formartted_datetime,
        "extra_info": result.extra_info,
    }

    # platform
    platform_logo = Path(__file__).parent / "resources" / "bilibili.png"
    data["platform"] = {
        "name": getattr(result.platform, "name", "bilibili"),
        "display_name": getattr(result.platform, "display_name", "哔哩哔哩"),
        "logo": platform_logo.as_uri() if platform_logo.exists() else None,
    }

    # author
    if result.author:
        avatar_path = await result.author.get_avatar_path()
        data["author"] = {
            "name": result.author.name,
            "avatar": avatar_path.as_uri() if avatar_path else None,
        }
    else:
        data["author"] = None

    # images (plain)
    images: list[str] = []
    for img in result.img_contents:
        path = await img.get_path()
        images.append(path.as_uri())
    data["images"] = images

    # graphics (text + image)
    graphics: list[dict[str, Any]] = []
    for g in result.graphics_contents:
        path = await g.get_path()
        graphics.append(
            {
                "path": path.as_uri(),
                "text": g.text,
                "alt": g.alt,
            }
        )
    data["graphics"] = graphics

    # cover (best-effort: prefer video cover, else first image)
    cover_path = await result.cover_path
    if cover_path:
        data["cover"] = cover_path.as_uri()
    elif images:
        data["cover"] = images[0]
    else:
        data["cover"] = None

    return data


class Renderer(ImageRenderer):
    @override
    async def render_image(self, result: ParseResult) -> bytes:
        data = await _resolve_result(result)
        return await template_to_pic(
            self.templates_dir.as_posix(),
            "bilibili.html.jinja",
            templates={"result": data},
            max_width=800,
            device_height=1200,
        )

