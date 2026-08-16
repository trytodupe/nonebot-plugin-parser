from __future__ import annotations

from typing import Any
from collections.abc import Callable, Awaitable

from nonebot import logger
from nonebot.plugin import get_plugin, get_loaded_plugins

from .config import GroupGateMode

_PLUGIN_NAME = "group_superuser_gate"
_EXPECTED_INTERFACE_VERSION = 2
_group_gate: Callable[[Any, Any], Awaitable[bool]] | None = None


def _find_gate_plugin():
    if plugin := get_plugin(_PLUGIN_NAME):
        return plugin
    return next(
        (
            plugin
            for plugin in get_loaded_plugins()
            if plugin.name == _PLUGIN_NAME or plugin.module_name.rsplit(".", 1)[-1] == _PLUGIN_NAME
        ),
        None,
    )


def configure_group_gate(mode: GroupGateMode) -> None:
    global _group_gate

    _group_gate = None
    if mode is GroupGateMode.off:
        logger.info("Parser sensitive group gate is disabled")
        return

    plugin = _find_gate_plugin()
    if plugin is None:
        if mode is GroupGateMode.required:
            raise RuntimeError("Parser requires the group_superuser_gate plugin, but it is not loaded")
        logger.info("Parser sensitive group gate is unavailable; continuing in auto mode")
        return

    interface_version = getattr(plugin.module, "GROUP_SUPERUSER_GATE_INTERFACE_VERSION", None)
    gate = getattr(plugin.module, "event_access_allowed", None)
    if interface_version != _EXPECTED_INTERFACE_VERSION or not callable(gate):
        raise RuntimeError(
            "Loaded group_superuser_gate has an incompatible interface "
            f"(expected {_EXPECTED_INTERFACE_VERSION}, got {interface_version!r})"
        )

    _group_gate = gate
    logger.success(f"Parser sensitive group gate active: provider={plugin.module_name}, interface={interface_version}")


async def gated_event_access_allowed(bot: Any, event: Any) -> bool:
    if _group_gate is None:
        return True
    return bool(await _group_gate(bot, event))


async def private_access_allowed(bot: Any, event: Any) -> bool:
    if hasattr(event, "group_id"):
        return True
    return await gated_event_access_allowed(bot, event)


__all__ = [
    "configure_group_gate",
    "gated_event_access_allowed",
    "private_access_allowed",
]
