"""Bilibili UP 主订阅模块

通过 APScheduler 定时轮询已订阅 UID 的最新动态，检测到新内容时
复用 parser 的解析 + 渲染管道，自动推送到对应 QQ 群。
"""

import json
import time
import asyncio
from pathlib import Path

from nonebot import logger, require
from nonebot.exception import ActionFailed, NetworkError

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_alconna")
from bilibili_api.user import User
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_alconna.uniseg import Target, SupportAdapter

from ..config import pconfig
from ..renders import get_renderer
from ..constants import PlatformEnum

_SUBS_PATH: Path = pconfig.data_dir / "bilibili_subscriptions.json"


def _extract_live_room_id(item: dict) -> str | None:
    module_dynamic = item.get("modules", {}).get("module_dynamic", {})
    additional = module_dynamic.get("additional")
    if not isinstance(additional, dict):
        return None

    live_rcmd = additional.get("live_rcmd")
    if not isinstance(live_rcmd, dict):
        return None

    content = live_rcmd.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            return None
    if not isinstance(content, dict):
        return None

    live_play_info = content.get("live_play_info")
    if not isinstance(live_play_info, dict):
        return None

    room_id = live_play_info.get("room_id")
    return str(room_id) if room_id else None


def _extract_url_from_item(item: dict) -> str | None:
    """从 get_dynamics_new 返回的 item 中提取可供 parser 解析的 URL"""
    id_str = item.get("id_str", "")
    major = item.get("modules", {}).get("module_dynamic", {}).get("major")

    if major is None:
        if room_id := _extract_live_room_id(item):
            return f"https://live.bilibili.com/{room_id}"
        return f"https://t.bilibili.com/{id_str}" if id_str else None

    major_type = major.get("type", "")

    if major_type == "MAJOR_TYPE_ARCHIVE":
        archive = major.get("archive", {})
        bvid = archive.get("bvid")
        if bvid:
            return f"https://www.bilibili.com/video/{bvid}"

    if major_type == "MAJOR_TYPE_OPUS":
        opus = major.get("opus", {})
        jump_url = opus.get("jump_url")
        if jump_url:
            return jump_url
        return f"https://t.bilibili.com/{id_str}"

    if major_type == "MAJOR_TYPE_ARTICLE":
        article = major.get("article", {})
        article_id = article.get("id")
        if article_id:
            return f"https://www.bilibili.com/read/cv{article_id}"

    if major_type == "MAJOR_TYPE_LIVE":
        live = major.get("live", {})
        room_id = live.get("roomid")
        if room_id:
            return f"https://live.bilibili.com/{room_id}"

    if major_type == "MAJOR_TYPE_UGC_SEASON":
        ugc_season = major.get("ugc_season", {})
        bvid = ugc_season.get("bvid")
        if bvid:
            return f"https://www.bilibili.com/video/{bvid}"

    if major_type == "MAJOR_TYPE_COMMON":
        common = major.get("common", {})
        jump_url = common.get("jump_url")
        if jump_url:
            return jump_url

    if major_type == "MAJOR_TYPE_PGC":
        pgc = major.get("pgc", {})
        epid = pgc.get("epid")
        if epid:
            return f"https://www.bilibili.com/bangumi/play/ep{epid}"

    if major_type == "MAJOR_TYPE_MUSIC":
        music = major.get("music", {})
        music_id = music.get("id")
        if music_id:
            return f"https://www.bilibili.com/audio/au{music_id}"

    # 兜底：用动态详情页 URL
    return f"https://t.bilibili.com/{id_str}" if id_str else None


class SubscriptionManager:
    """B 站订阅管理器

    内存中维护 (scope, group_id) → set[uid] 和 uid → last_dynamic_id 索引，
    持久化到 data_dir / bilibili_subscriptions.json。
    """

    def __init__(self) -> None:
        self._path = _SUBS_PATH
        self._subs: dict[tuple[str, str], set[str]] = {}
        self._last_seen: dict[str, str] = {}
        self._load()

    # ---- persistence ----

    def _load(self) -> None:
        if not self._path.exists():
            self._path.write_text(json.dumps({"subscriptions": [], "last_seen": {}}))

        try:
            data = json.loads(self._path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning(f"订阅文件损坏，重置: {self._path}")
            data = {"subscriptions": [], "last_seen": {}}

        for entry in data.get("subscriptions", []):
            key = (entry["scope"], entry["group_id"])
            self._subs.setdefault(key, set()).add(entry["uid"])

        for uid, info in data.get("last_seen", {}).items():
            self._last_seen[uid] = info.get("last_dynamic_id", "0")

        logger.info(
            f"已加载 {sum(len(v) for v in self._subs.values())} 条订阅，{len(self._last_seen)} 个 UID 的检查记录"
        )

    def _save(self) -> None:
        subscriptions: list[dict] = []
        for (scope, group_id), uids in self._subs.items():
            for uid in uids:
                subscriptions.append({"scope": scope, "group_id": group_id, "uid": uid})

        last_seen = {uid: {"last_dynamic_id": lid, "last_checked": time.time()} for uid, lid in self._last_seen.items()}

        self._path.write_text(
            json.dumps(
                {"subscriptions": subscriptions, "last_seen": last_seen},
                ensure_ascii=False,
                indent=2,
            )
        )

    # ---- subscription CRUD ----

    def add_sub(self, scope: str, group_id: str, uid: str) -> None:
        key = (scope, group_id)
        self._subs.setdefault(key, set()).add(uid)
        self._save()
        logger.info(f"订阅: {scope}_{group_id} -> UID {uid}")

    def remove_sub(self, scope: str, group_id: str, uid: str) -> bool:
        key = (scope, group_id)
        if key not in self._subs or uid not in self._subs[key]:
            return False
        self._subs[key].discard(uid)
        if not self._subs[key]:
            del self._subs[key]
        self._save()
        logger.info(f"取消订阅: {scope}_{group_id} -> UID {uid}")
        return True

    def get_subs_for_group(self, scope: str, group_id: str) -> list[str]:
        return sorted(self._subs.get((scope, group_id), set()))

    def get_groups_for_uid(self, uid: str) -> list[tuple[str, str]]:
        return [key for key, uids in self._subs.items() if uid in uids]

    def get_all_uids(self) -> list[str]:
        seen: set[str] = set()
        for uids in self._subs.values():
            seen.update(uids)
        return sorted(seen)

    # ---- last seen tracking ----

    def get_last_seen(self, uid: str) -> str:
        return self._last_seen.get(uid, "0")

    def set_last_seen(self, uid: str, dynamic_id: str) -> None:
        self._last_seen[uid] = dynamic_id
        self._save()

    async def init_last_seen(self, uid: str) -> str | None:
        """为新订阅的 UID 立即初始化 last_seen 书签。

        消除「订阅 → 首次轮询」之间的窗口期：
        如果 UP 主在这个窗口内发新内容，不会被误标记为「历史」。

        Returns:
            最新 dynamic_id，如果获取失败则返回 None。
        """
        if self._last_seen.get(uid, "0") != "0":
            return self._last_seen[uid]  # 已经初始化过

        try:
            user = User(int(uid))
            data = await user.get_dynamics_new(offset="")
            items = data.get("items", [])
            if items:
                newest = items[0].get("id_str", "0")
                self._last_seen[uid] = newest
                self._save()
                logger.info(f"初始化 UID {uid} last_seen={newest}")
                return newest
            return None
        except Exception:
            logger.exception(f"初始化 UID {uid} last_seen 失败，将在首次轮询时重试")
            return None


# 模块级单例
_sub_manager: SubscriptionManager | None = None


def get_subscription_manager() -> SubscriptionManager:
    global _sub_manager
    if _sub_manager is None:
        _sub_manager = SubscriptionManager()
    return _sub_manager


# ---- APScheduler 轮询任务 ----


@scheduler.scheduled_job(
    "interval",
    seconds=pconfig.bili_sub_interval,
    id="parser-bili-sub-check",
)
async def check_bilibili_updates():
    if not pconfig.bili_sub_enabled:
        return

    sub_mgr = get_subscription_manager()
    uids = sub_mgr.get_all_uids()
    if not uids:
        return

    # 延迟导入，避免循环引用
    from ..parsers import BilibiliParser
    from ..matchers import get_parser_by_type

    parser = get_parser_by_type(BilibiliParser)
    renderer = get_renderer(PlatformEnum.BILIBILI)

    logger.debug(f"开始检查 {len(uids)} 个 UID 的动态更新")

    for uid in uids:
        try:
            await _check_single_uid(uid, sub_mgr, parser, renderer)
        except Exception:
            logger.exception(f"检查 UID {uid} 更新时出错")
        # UID 间延迟，避免触发 B 站风控
        await asyncio.sleep(2)


async def _check_single_uid(
    uid: str,
    sub_mgr: SubscriptionManager,
    parser,
    renderer,
) -> None:
    user = User(int(uid))
    data = await user.get_dynamics_new(offset="")

    items = data.get("items")
    if not items:
        return

    last_seen = sub_mgr.get_last_seen(uid)

    # 首次订阅：只记录最新 ID，不发历史内容
    if last_seen == "0":
        newest = items[0].get("id_str", "0")
        sub_mgr.set_last_seen(uid, newest)
        logger.info(f"首次检查 UID {uid}，记录最新动态 {newest}，跳过历史")
        return

    # 找出新动态（items 按时间倒序）
    new_items = []
    for item in items:
        id_str = item.get("id_str", "0")
        if int(id_str) <= int(last_seen):
            break
        new_items.append(item)

    if not new_items:
        return

    # 先更新 last_seen（避免处理失败时重复推送）
    newest_id = items[0].get("id_str", last_seen)
    sub_mgr.set_last_seen(uid, newest_id)

    groups = sub_mgr.get_groups_for_uid(uid)
    if not groups:
        return

    logger.info(f"UID {uid} 有 {len(new_items)} 条新动态，推送到 {len(groups)} 个群")

    # 按时间正序发送（最旧的先发）
    for item in reversed(new_items):
        url = _extract_url_from_item(item)
        if not url:
            continue

        dynamic_id_str = item.get("id_str", "?")
        dynamic_type = item.get("type", "?")

        # 解析
        try:
            keyword, searched = parser.search_url(url)
            result = await parser.parse(keyword, searched)
        except Exception:
            logger.exception(f"解析动态失败 UID={uid} id={dynamic_id_str} type={dynamic_type} url={url}")
            continue

        # 渲染 + 发送到每个订阅群
        for scope, group_id in groups:
            try:
                target = Target(
                    group_id,
                    scope=scope,
                    adapter=SupportAdapter.onebot11,
                )
                async for message in renderer.render_messages(result):
                    await message.send(target=target)
                # 群间短延迟，避免 QQ 频率限制
                await asyncio.sleep(0.5)
            except ActionFailed as e:
                logger.warning(f"发送失败 {scope}_{group_id}: bot 可能不在群内或无权限 ({e})")
            except NetworkError as e:
                logger.warning(f"网络错误 {scope}_{group_id}: {e}")
