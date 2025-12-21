import re
from typing import Any, ClassVar
from itertools import chain

from httpx import AsyncClient

from .base import BaseParser, PlatformEnum, handle
from .data import Platform, ParseResult
from ..exception import ParseException


class TwitterParser(BaseParser):
    # 平台信息
    platform: ClassVar[Platform] = Platform(name=PlatformEnum.TWITTER, display_name="小蓝鸟")

    async def _req_xdown_api(self, url: str) -> dict[str, Any]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://xdown.app",
            "Referer": "https://xdown.app/",
            **self.headers,
        }
        data = {"q": url, "lang": "zh-cn"}
        async with AsyncClient(headers=headers, timeout=self.timeout) as client:
            url = "https://xdown.app/api/ajaxSearch"
            response = await client.post(url, data=data)
            return response.json()

    async def _req_oembed(self, url: str) -> dict[str, Any] | None:
        """Fetch tweet metadata via Twitter/X oEmbed (no auth)."""
        headers = {
            "Accept": "application/json",
            "Referer": "https://publish.twitter.com/",
            **self.headers,
        }
        params = {"url": url}
        async with AsyncClient(headers=headers, timeout=self.timeout) as client:
            resp = await client.get("https://publish.twitter.com/oembed", params=params)
            if resp.status_code != 200:
                return None
            try:
                return resp.json()
            except Exception:
                return None

    @staticmethod
    def _build_avatar_url(screen_name: str) -> str:
        # Unavatar provides a stable, auth-free avatar proxy for many platforms.
        # /twitter/<name> redirects to /x/<name>; use /x/ directly.
        return f"https://unavatar.io/x/{screen_name}"

    @staticmethod
    def _extract_oembed_text(oembed_html: str) -> str | None:
        """Extract tweet text from oEmbed HTML blockquote."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(oembed_html, "html.parser")
        p = soup.find("p")
        if not p:
            return None
        text = p.get_text(" ", strip=True)
        return text or None

    @handle("x.com", r"https?://x.com/[0-9-a-zA-Z_]{1,20}/status/([0-9]+)")
    async def _parse(self, searched: re.Match[str]) -> ParseResult:
        # 从匹配对象中获取原始URL
        url = searched.group(0)
        resp = await self._req_xdown_api(url)
        if resp.get("status") != "ok":
            raise ParseException("解析失败")

        html_content = resp.get("data")

        if html_content is None:
            raise ParseException("解析失败, 数据为空")

        result = self.parse_twitter_html(html_content)
        result.url = url

        # Enrich author/text via oEmbed (xdown HTML only provides media download info).
        try:
            if oembed := await self._req_oembed(url):
                author_name = str(oembed.get("author_name") or "").strip() or None
                author_url = str(oembed.get("author_url") or "").strip() or None
                screen_name = author_url.rsplit("/", 1)[-1] if author_url and "/" in author_url else None
                if screen_name:
                    display = author_name or screen_name
                    author_display = display if display.lower() == screen_name.lower() else f"{display} (@{screen_name})"
                    result.author = self.create_author(author_display, avatar_url=self._build_avatar_url(screen_name))
                elif author_name:
                    result.author = self.create_author(author_name)

                if not result.text and (oembed_html := oembed.get("html")):
                    text = self._extract_oembed_text(str(oembed_html))
                    if text:
                        result.text = text

                if not result.title:
                    result.title = author_name or screen_name
        except Exception:
            # Best-effort; keep media results even if oEmbed is unavailable.
            pass

        return result

    def parse_twitter_html(self, html_content: str) -> ParseResult:
        """解析 Twitter HTML 内容

        Args:
            html_content (str): Twitter HTML 内容

        Returns:
            ParseResult: 解析结果
        """
        from bs4 import Tag, BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")

        # 初始化数据
        title = None
        cover_url = None
        video_url = None
        images_urls = []
        dynamic_urls = []

        # 1. 提取缩略图链接
        thumb_tag = soup.find("img")
        if isinstance(thumb_tag, Tag):
            if cover := thumb_tag.get("src"):
                cover_url = str(cover)

        # 2. 提取下载链接
        tw_button_tags = soup.find_all("a", class_="tw-button-dl")
        abutton_tags = soup.find_all("a", class_="abutton")
        for tag in chain(tw_button_tags, abutton_tags):
            if not isinstance(tag, Tag):
                continue
            href = tag.get("href")
            if href is None:
                continue

            href = str(href)
            text = tag.get_text(strip=True)
            if "下载 MP4" in text:
                video_url = href
                break
            elif "下载图片" in text:
                images_urls.append(href)
            elif "下载 gif" in text:
                dynamic_urls.append(href)

        # 3. 提取标题
        title_tag = soup.find("h3")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 简洁的构建方式
        contents = []

        # 添加视频内容
        if video_url:
            if video_content := self.create_video_content(video_url, cover_url):
                contents.append(video_content)

        # 添加图片内容
        if images_urls:
            contents.extend(self.create_image_contents(images_urls))

        # 添加动态内容
        if dynamic_urls:
            contents.extend(self.create_dynamic_contents(dynamic_urls))

        return self.result(
            title=title,
            author=None,
            contents=contents,
        )
        # # 4. 提取Twitter ID
        # twitter_id_input = soup.find("input", {"id": "TwitterId"})
        # if (
        #     twitter_id_input
        #     and isinstance(twitter_id_input, Tag)
        #     and (value := twitter_id_input.get("value"))
        #     and isinstance(value, str)
        # ):
