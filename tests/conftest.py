import os
import shutil
import tomllib
from pathlib import Path

import pytest
from pytest_asyncio import is_async_test

if Path(".env.dev").exists:
    os.environ["ENVIRONMENT"] = "dev"
else:
    os.environ["ENVIRONMENT"] = "test"


def pytest_collection_modifyitems(items: list[pytest.Item]):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init: None):
    import nonebot
    from nonebot.adapters.onebot.v11 import Adapter as OnebotV11Adapter

    # 加载适配器
    driver = nonebot.get_driver()
    driver.register_adapter(OnebotV11Adapter)

    # 加载插件
    nonebot.load_from_toml("pyproject.toml")


@pytest.fixture(scope="session")
def project_temp_dir() -> Path:
    """Repo-root temp directory used for test artifacts."""
    return Path(__file__).resolve().parents[1] / "temp"


@pytest.fixture(scope="session")
def project_temp_config_path(project_temp_dir: Path) -> Path:
    return project_temp_dir / "test_config.toml"


@pytest.fixture(scope="session")
def project_temp_config(project_temp_config_path: Path) -> dict:
    if not project_temp_config_path.exists():
        raise FileNotFoundError(f"Missing test config: {project_temp_config_path}")
    with project_temp_config_path.open("rb") as f:
        return tomllib.load(f)


@pytest.fixture(autouse=True)
def cleanup_project_temp_dir(project_temp_dir: Path, project_temp_config_path: Path):
    """
    At the start of every test, clear everything under repo-root `temp/` except the config file.

    This keeps artifacts from the current run inspectable, and avoids stale files from previous runs.
    """
    project_temp_dir.mkdir(parents=True, exist_ok=True)

    for child in project_temp_dir.iterdir():
        if child == project_temp_config_path:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
