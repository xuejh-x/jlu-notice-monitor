from pathlib import Path

import pytest

from app.__main__ import build_parser
from app.config import BACKEND_DIR, load_yaml
from app.schemas.notice import NoticeCandidate
from app.sources.base import LoginExpiredError, SourceError
from app.sources.oa import OASource


def oa_config() -> dict:
    return next(item for item in load_yaml("sources.yaml")["sources"] if item["code"] == "oa")


def test_oa_is_disabled_and_profile_is_local_data() -> None:
    config = oa_config()
    source = OASource(config)
    assert config["enabled"] is False
    assert source.profile_path == BACKEND_DIR / "data" / "browser_profile" / "oa"


def test_oa_login_command_is_registered() -> None:
    assert build_parser().parse_args(["oa-login"]).command == "oa-login"
    assert hasattr(OASource, "login_setup")
    assert hasattr(OASource, "check_login")


@pytest.mark.asyncio
async def test_oa_login_expired_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    source = OASource(oa_config())

    async def not_logged_in() -> bool:
        return False

    monkeypatch.setattr(source, "check_login", not_logged_in)
    with pytest.raises(LoginExpiredError, match="OA_LOGIN_EXPIRED"):
        await source.fetch_list()


@pytest.mark.asyncio
async def test_oa_valid_session_stays_unconfigured_until_dom_is_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = OASource(oa_config())

    async def logged_in() -> bool:
        return True

    monkeypatch.setattr(source, "check_login", logged_in)
    with pytest.raises(SourceError, match="OA_UNCONFIGURED"):
        await source.fetch_list()
    with pytest.raises(SourceError, match="OA_UNCONFIGURED"):
        await source.fetch_detail(NoticeCandidate(title="x", url="https://oa.jlu.edu.cn/x"))

