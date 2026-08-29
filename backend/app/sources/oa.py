from __future__ import annotations

from app.config import BACKEND_DIR, get_settings
from app.schemas.notice import NoticeCandidate
from app.sources.base import LoginExpiredError, NoticeSource, SourceError


class OASource(NoticeSource):
    """OA adapter using a user-owned persistent Playwright profile."""

    def __init__(self, config: dict[str, object]) -> None:
        super().__init__(config)
        self.profile_path = BACKEND_DIR / "data" / "browser_profile" / "oa"
        self.context = None
        self.playwright = None

    async def _ensure_context(self, headless: bool | None = None) -> object:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise SourceError("OA requires: pip install -e .[oa] and playwright install chromium") from exc
        if self.context is None:
            self.profile_path.mkdir(parents=True, exist_ok=True)
            self.playwright = await async_playwright().start()
            configured = get_settings().oa_headless if headless is None else headless
            self.context = await self.playwright.chromium.launch_persistent_context(
                str(self.profile_path), headless=configured, channel="msedge"
            )
        return self.context

    async def login_setup(self) -> None:
        context = await self._ensure_context(headless=False)
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(self.base_url)
        print("请在浏览器中完成吉林大学统一身份认证；完成后回到此窗口按 Enter。")
        input()
        await context.close()
        self.context = None

    async def check_login(self) -> bool:
        context = await self._ensure_context()
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(self.base_url, wait_until="domcontentloaded")
        current = page.url.lower()
        text = (await page.locator("body").inner_text()).lower()
        return not ("login" in current or "统一身份认证" in text or "用户登录" in text)

    async def _page_html(self, url: str) -> str:
        context = await self._ensure_context()
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url, wait_until="networkidle")
        html = await page.content()
        current = page.url.lower()
        text = (await page.locator("body").inner_text()).lower()
        if "login" in current or "统一身份认证" in text or "用户登录" in text:
            raise LoginExpiredError("OA_LOGIN_EXPIRED")
        return html

    async def fetch_list(self) -> list[NoticeCandidate]:
        if not await self.check_login():
            raise LoginExpiredError("OA_LOGIN_EXPIRED")
        raise SourceError("OA_UNCONFIGURED: 登录后的通知列表 DOM 尚未在校园网络中验证")

    async def fetch_detail(self, notice: NoticeCandidate) -> NoticeCandidate:
        raise SourceError("OA_UNCONFIGURED: 登录后的通知详情 DOM 尚未验证")

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()


OaSource = OASource
