import re
from typing import ClassVar

from .base import BaseParser, MediaType, PlatformEnum, handle
from .data import Author, Platform, VideoContent
from ..download import YTDLP_DOWNLOADER


class TikTokParser(BaseParser):
    # 平台信息
    platform: ClassVar[Platform] = Platform(name=PlatformEnum.TIKTOK, display_name="TikTok")

    @handle("tiktok.com", r"(?:https?://)?(www|vt|vm)\.tiktok\.com/[A-Za-z0-9._?%&+\-=/#@]*")
    async def _parse(self, searched: re.Match[str]):
        # 从匹配对象中获取原始URL
        url, prefix = searched.group(0), searched.group(1)

        if prefix in ("vt", "vm"):
            url = await self.get_redirect_url(url)

        # 获取视频信息
        video_info = await YTDLP_DOWNLOADER.extract_video_info(url)

        contents = []
        if self.allows_media(MediaType.VIDEO):
            video = YTDLP_DOWNLOADER.download_video(url)
            video_content = self.create_video_content(
                video,
                video_info.thumbnail,
                duration=video_info.duration,
            )
            if video_content:
                contents.append(video_content)
        else:
            contents.extend(self.create_image_contents([video_info.thumbnail]))

        return self.result(
            title=video_info.title,
            author=Author(name=video_info.channel),
            contents=contents,
            timestamp=video_info.timestamp,
        )
