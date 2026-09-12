from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Any, Awaitable, Callable
from urllib.parse import quote

import httpx


class ChromeSessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChromeEnvironment:
    chrome_available: bool
    desktop_runtime_available: bool
    adapter_available: bool
    browser_name: str | None
    error_code: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def find_chrome() -> Path | None:
    configured = os.getenv("NOTICE_HUB_CHROME_PATH", "").strip()
    candidates: list[Path] = [Path(configured)] if configured else []
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.getenv(variable, "").strip()
        if root:
            candidates.append(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")
    for executable in ("google-chrome", "chrome", "chrome.exe", "chromium", "chromium-browser"):
        located = shutil.which(executable)
        if located:
            candidates.append(Path(located))
    if os.name == "nt":
        try:
            import winreg

            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                        value, _ = winreg.QueryValueEx(key, None)
                        candidates.append(Path(str(value)))
                except OSError:
                    continue
        except ImportError:
            pass
    return next((path.resolve() for path in candidates if path.is_file()), None)


def inspect_chrome_environment() -> ChromeEnvironment:
    chrome = find_chrome()
    if chrome is None:
        return ChromeEnvironment(False, True, True, None, "OA_CHROME_NOT_FOUND", "未检测到 Google Chrome。")
    try:
        from websockets.asyncio.client import connect as _  # noqa: F401
    except ImportError:
        return ChromeEnvironment(True, True, False, "Google Chrome", "OA_LOGIN_ADAPTER_UNAVAILABLE", "OA 登录组件不可用。")
    return ChromeEnvironment(True, True, True, "Google Chrome", None, "Chrome、Desktop Runtime 与 OA 登录组件均已就绪。")


class ChromeCDPSession:
    """A small CDP client that only launches the user's installed Chrome binary."""

    def __init__(
        self,
        profile_path: Path,
        *,
        headless: bool,
        request_guard: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        self.profile_path = profile_path
        self.headless = headless
        self.process: subprocess.Popen[bytes] | None = None
        self.port: int | None = None
        self.browser_ws_url: str | None = None
        self.page_ws_url: str | None = None
        self.websocket: Any | None = None
        self._message_id = 0
        self.request_guard = request_guard

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            return int(server.getsockname()[1])

    async def start(self, initial_url: str = "about:blank") -> None:
        environment = inspect_chrome_environment()
        if environment.error_code:
            raise ChromeSessionError(environment.error_code)
        chrome = find_chrome()
        if chrome is None:
            raise ChromeSessionError("OA_CHROME_NOT_FOUND")
        self.profile_path.mkdir(parents=True, exist_ok=True)
        self.port = self._free_port()
        arguments = [
            str(chrome),
            f"--remote-debugging-port={self.port}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={self.profile_path}",
            "--remote-allow-origins=http://127.0.0.1",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if self.headless:
            arguments.extend(["--headless=new", "--disable-gpu"])
        arguments.append(initial_url)
        try:
            self.process = subprocess.Popen(arguments, close_fds=True)
        except OSError as exc:
            raise ChromeSessionError("OA_CHROME_START_FAILED") from exc
        await self._connect(initial_url)

    async def _connect(self, initial_url: str) -> None:
        assert self.port is not None
        endpoint = f"http://127.0.0.1:{self.port}"
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=1) as client:
            for _ in range(80):
                try:
                    version = (await client.get(f"{endpoint}/json/version")).json()
                    self.browser_ws_url = str(version["webSocketDebuggerUrl"])
                    pages = (await client.get(f"{endpoint}/json/list")).json()
                    page = next((item for item in pages if item.get("type") == "page"), None)
                    if page is None:
                        page = (await client.put(f"{endpoint}/json/new?{quote(initial_url, safe=':/?=&')}")).json()
                    self.page_ws_url = str(page["webSocketDebuggerUrl"])
                    break
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                    last_error = exc
                    await asyncio.sleep(0.1)
            else:
                await self.close()
                raise ChromeSessionError("OA_CHROME_CDP_UNAVAILABLE") from last_error
        from websockets.asyncio.client import connect

        self.websocket = await connect(self.page_ws_url, max_size=16 * 1024 * 1024)
        await self.command("Page.enable")
        await self.command("Runtime.enable")
        await self.command("Network.enable")
        if self.request_guard is not None:
            await self.command("Fetch.enable", {"patterns": [{"urlPattern": "http://*"}, {"urlPattern": "https://*"}]})

    async def command(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.websocket is None:
            raise ChromeSessionError("OA_CHROME_SESSION_CLOSED")
        self._message_id += 1
        message_id = self._message_id
        await self.websocket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            try:
                response = json.loads(await self.websocket.recv())
            except Exception as exc:
                raise ChromeSessionError("OA_CHROME_SESSION_CLOSED") from exc
            if response.get("method") == "Fetch.requestPaused":
                await self._handle_paused_request(dict(response.get("params") or {}))
                continue
            if response.get("id") != message_id:
                continue
            if response.get("error"):
                raise ChromeSessionError(f"OA_CDP_{method.replace('.', '_').upper()}_FAILED")
            return dict(response.get("result") or {})

    async def _handle_paused_request(self, params: dict[str, Any]) -> None:
        if self.websocket is None or self.request_guard is None:
            return
        request_id = str(params.get("requestId") or "")
        url = str((params.get("request") or {}).get("url") or "")
        try:
            allowed = bool(request_id and await self.request_guard(url))
        except Exception:
            allowed = False
        self._message_id += 1
        if allowed:
            payload = {"id": self._message_id, "method": "Fetch.continueRequest", "params": {"requestId": request_id}}
        else:
            payload = {"id": self._message_id, "method": "Fetch.failRequest", "params": {"requestId": request_id, "errorReason": "BlockedByClient"}}
        await self.websocket.send(json.dumps(payload))

    async def navigate(self, url: str, *, wait_seconds: float = 15) -> tuple[str, str, str]:
        await self.command("Page.navigate", {"url": url})
        deadline = asyncio.get_running_loop().time() + wait_seconds
        while asyncio.get_running_loop().time() < deadline:
            state = await self.evaluate("document.readyState")
            if state in {"interactive", "complete"}:
                break
            await asyncio.sleep(0.15)
        await asyncio.sleep(0.35)
        html = str(await self.evaluate("document.documentElement.outerHTML") or "")
        current = str(await self.evaluate("location.href") or url)
        text = str(await self.evaluate("document.body ? document.body.innerText : ''") or "")
        return html, current, text

    async def evaluate(self, expression: str) -> Any:
        result = await self.command("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return (result.get("result") or {}).get("value")

    async def wait_for_selector(self, selector: str, *, timeout_seconds: float = 15) -> tuple[str, str, str]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        expression = f"document.querySelector({json.dumps(selector)}) !== null"
        while asyncio.get_running_loop().time() < deadline:
            if await self.evaluate(expression):
                html = str(await self.evaluate("document.documentElement.outerHTML") or "")
                current = str(await self.evaluate("location.href") or "")
                text = str(await self.evaluate("document.body ? document.body.innerText : ''") or "")
                return html, current, text
            await asyncio.sleep(0.25)
        raise ChromeSessionError("CLOUD_RENDER_SELECTOR_TIMEOUT")

    async def cookies(self) -> list[dict[str, Any]]:
        return list((await self.command("Network.getAllCookies")).get("cookies") or [])

    async def restore_cookies(self, cookies: list[dict[str, Any]]) -> None:
        allowed = {"name", "value", "url", "domain", "path", "secure", "httpOnly", "sameSite", "expires", "priority", "sameParty", "sourceScheme", "sourcePort", "partitionKey"}
        sanitized = [{key: value for key, value in cookie.items() if key in allowed} for cookie in cookies]
        if sanitized:
            await self.command("Network.setCookies", {"cookies": sanitized})

    async def close(self) -> None:
        if self.websocket is not None:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None
        if self.browser_ws_url:
            try:
                from websockets.asyncio.client import connect

                async with connect(self.browser_ws_url) as browser:
                    await browser.send(json.dumps({"id": 1, "method": "Browser.close"}))
            except Exception:
                pass
        if self.process is not None:
            try:
                await asyncio.to_thread(self.process.wait, 3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
            self.process = None
