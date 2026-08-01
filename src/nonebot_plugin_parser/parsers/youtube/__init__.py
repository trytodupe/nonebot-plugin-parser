import re
from typing import ClassVar
from pathlib import Path

from httpx import AsyncClient

from ..base import Platform, BaseParser, PlatformEnum, handle, pconfig
from ..cookie import save_cookies_with_netscape
from ...download import yt_dlp_downloader


def detect_youtube_cookiefile() -> Path | None:
    candidates = (
        pconfig.data_dir / "ytb_cookies.txt",
        pconfig.data_dir / "cookies.txt",
        pconfig.config_dir / "ytb_cookies.txt",
    )
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


class YouTubeParser(BaseParser):
    platform: ClassVar[Platform] = Platform(name=PlatformEnum.YOUTUBE, display_name="油管")

    def __init__(self):
        super().__init__()
        self.cookies_file: Path | None = None
        if pconfig.ytb_ck:
            self.cookies_file = pconfig.config_dir / "ytb_cookies.txt"
            save_cookies_with_netscape(
                pconfig.ytb_ck,
                self.cookies_file,
                "youtube.com",
            )
        else:
            self.cookies_file = detect_youtube_cookiefile()

    @handle("youtu", r"youtu\.be/[A-Za-z\d\._\?%&\+\-=/#]+")
    @handle("youtube", r"youtube\.com/(?:watch|shorts)(?:/[A-Za-z\d_\-]+|\?v=[A-Za-z\d_\-]+)")
    async def _parse_video(self, searched: re.Match[str]):
        url = f"https://{searched.group(0)}"
        return await self.parse_video(url)

    async def parse_video(self, url: str):
        video_info = await yt_dlp_downloader.extract_video_info(url, self.cookies_file)
        author = await self._fetch_author_info(video_info.channel_id)

        result = self.result(
            author=author,
            title=video_info.title,
            timestamp=video_info.timestamp,
        )

        if video_info.duration <= pconfig.duration_maximum:
            video = yt_dlp_downloader.download_video(url, self.cookies_file)
            result.video = self.create_video(
                video,
                video_info.thumbnail,
                video_info.duration,
            )
        else:
            result.contents.extend(self.create_images([video_info.thumbnail]))

        return result

    async def _fetch_author_info(self, channel_id: str):
        from . import meta

        url = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false"
        payload = {
            "context": {
                "client": {
                    "hl": "zh-HK",
                    "gl": "US",
                    "deviceMake": "Apple",
                    "deviceModel": "",
                    "clientName": "WEB",
                    "clientVersion": "2.20251002.00.00",
                    "osName": "Macintosh",
                    "osVersion": "10_15_7",
                },
                "user": {"lockedSafetyMode": False},
                "request": {
                    "useSsl": True,
                    "internalExperimentFlags": [],
                    "consistencyTokenJars": [],
                },
            },
            "browseId": channel_id,
        }

        async with AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        browse = meta.decoder.decode(response.content)
        return self.create_author(browse.name, browse.avatar_url, browse.description)
