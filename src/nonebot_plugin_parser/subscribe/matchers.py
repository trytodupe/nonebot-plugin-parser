"""订阅管理命令: ttd sub add/remove/list"""

from nonebot import logger, on_command
from nonebot.rule import to_me
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from bilibili_api.user import User
from nonebot.permission import SUPERUSER
from nonebot_plugin_uninfo import ADMIN, Session, UniSession

from . import get_subscription_manager

sub_cmd = on_command("sub", rule=to_me(), permission=SUPERUSER | ADMIN(), block=True)


@sub_cmd.handle()
async def _(
    matcher: Matcher,
    args: Message = CommandArg(),
    session: Session = UniSession(),
):
    """ttd sub add/remove/list — B 站 UP 主订阅管理"""
    if session.scene.is_private:
        await matcher.finish("订阅功能仅在群聊中可用")

    text = args.extract_plain_text().strip()
    parts = text.split(maxsplit=1)
    action = parts[0].lower() if parts else ""
    uid_arg = parts[1].strip() if len(parts) > 1 else ""

    sub_mgr = get_subscription_manager()
    scope = session.scope
    group_id = session.scene_path

    if action == "add":
        await _handle_add(matcher, sub_mgr, scope, group_id, uid_arg)
    elif action == "remove":
        await _handle_remove(matcher, sub_mgr, scope, group_id, uid_arg)
    elif action == "list":
        await _handle_list(matcher, sub_mgr, scope, group_id)
    else:
        await matcher.finish("用法: ttd sub add/remove <uid> 或 ttd sub list")


async def _handle_add(
    matcher: Matcher,
    sub_mgr,
    scope: str,
    group_id: str,
    uid: str,
) -> None:
    if not uid.isdigit():
        await matcher.finish("请提供有效的 B 站用户 UID（纯数字）")

    # 检查是否已订阅
    existing = sub_mgr.get_subs_for_group(scope, group_id)
    if uid in existing:
        await matcher.finish(f"UID {uid} 已在本群订阅列表中，无需重复添加")

    sub_mgr.add_sub(scope, group_id, uid)

    # 立即初始化 last_seen 书签，消除「订阅 → 首次轮询」之间的窗口期
    await sub_mgr.init_last_seen(uid)
    await sub_mgr.init_live_state(uid)

    # 获取用户名以给出友好反馈
    name = ""
    try:
        user = User(int(uid))
        info = await user.get_user_info()
        name = info.get("name", "")
    except Exception:
        logger.exception(f"获取 UID {uid} 用户信息失败")

    if name:
        await matcher.finish(f"已订阅 {name}（UID: {uid}）")
    else:
        await matcher.finish(f"已订阅 UID: {uid}（无法获取用户名，订阅已生效）")


async def _handle_remove(
    matcher: Matcher,
    sub_mgr,
    scope: str,
    group_id: str,
    uid: str,
) -> None:
    if not uid.isdigit():
        await matcher.finish("请提供有效的 B 站用户 UID（纯数字）")

    removed = sub_mgr.remove_sub(scope, group_id, uid)
    if removed:
        await matcher.finish(f"已取消订阅 UID: {uid}")
    else:
        await matcher.finish(f"本群未订阅 UID: {uid}")


async def _handle_list(
    matcher: Matcher,
    sub_mgr,
    scope: str,
    group_id: str,
) -> None:
    uids = sub_mgr.get_subs_for_group(scope, group_id)
    if not uids:
        await matcher.finish("本群暂无 B 站订阅")

    lines: list[str] = ["本群 B 站订阅列表:"]
    for uid in uids:
        try:
            user = User(int(uid))
            info = await user.get_user_info()
            name = info.get("name", "?")
            lines.append(f"  {name}（UID: {uid}）")
        except Exception:
            lines.append(f"  UID: {uid}")

    await matcher.finish("\n".join(lines))
