import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Persistent browser profile: logins made in the visible browser are reused by later headless runs
PROFILE_DIR = Path(__file__).parent / ".browser_profile"

# URL fragments of login / auth-wall / 2FA pages (LinkedIn, Google, generic)
LOGIN_URL_HINTS = ("login", "signin", "sign-in", "authwall", "checkpoint", "/uas/", "accounts.google.com")


class LoginRequiredError(RuntimeError):
    pass


def _run_in_browser_thread(coro_fn, *args):
    """
    Run a Playwright coroutine to completion in a dedicated thread with its own event loop.

    This works even when the caller already has a running loop (e.g. Jupyter). On Windows the loop
    must be a ProactorEventLoop, since Playwright launches the browser as a subprocess and Jupyter
    switches the global policy to the selector loop, which cannot do that.
    """
    def _run():
        loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro_fn(*args))
        finally:
            loop.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_run).result()


def _fetch_static_html(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    return response.content


async def _wait_until_settled(page, timeout_ms=15_000):
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        # Some sites (LinkedIn included) never go fully idle; use what has rendered so far
        pass


async def _scroll_to_bottom(page, max_rounds=20):
    """Scroll until the page stops growing, so lazy-loaded sections get rendered."""
    previous_height = 0
    for _ in range(max_rounds):
        height = await page.evaluate("document.body.scrollHeight")
        if height == previous_height:
            break
        previous_height = height
        await page.mouse.wheel(0, height)
        await page.wait_for_timeout(800)


async def _needs_login(page):
    if any(hint in page.url.lower() for hint in LOGIN_URL_HINTS):
        return True
    return await page.locator("input[type=password]:visible").count() > 0


async def _open_profile(p, headless):
    return await p.chromium.launch_persistent_context(
        PROFILE_DIR, headless=headless, user_agent=USER_AGENT, viewport={"width": 1280, "height": 900}
    )


async def _wait_for_user_login(page, url, timeout_s):
    """Poll the visible browser until the user is past the login wall and back on the target page."""
    print("Login required: log in in the opened browser window. The page will be captured automatically.")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if page.is_closed():
            raise LoginRequiredError("Browser window closed before login completed")
        try:
            if not await _needs_login(page):
                # Logins often land on a home/feed page: go back to the requested page and re-check
                if urlparse(page.url).path.rstrip("/") != urlparse(url).path.rstrip("/"):
                    await page.goto(url, wait_until="domcontentloaded")
                    continue
                # Auth walls can be client-side redirects: confirm once the page has settled
                await _wait_until_settled(page, timeout_ms=5_000)
                if not await _needs_login(page):
                    return
                continue
        except PlaywrightError:
            # Page is mid-navigation (e.g. the login form was just submitted); check again shortly
            pass
        await asyncio.sleep(1)
    raise LoginRequiredError(f"Login not completed within {timeout_s}s")


async def _fetch_rendered_html(url, interactive, login_timeout_s):
    """
    Load the page with a real browser so client-side JavaScript runs, then return the DOM as HTML.

    First tries headless with the saved profile. If a login wall shows up and interactive is True,
    reopens the page in a visible window and waits for the user to log in.
    """
    async with async_playwright() as p:
        context = await _open_profile(p, headless=True)
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await _wait_until_settled(page)
            if not await _needs_login(page):
                await _scroll_to_bottom(page)
                return await page.content()
        finally:
            await context.close()

        if not interactive:
            raise LoginRequiredError(f"{url} requires a login (call with interactive=True to log in)")

        context = await _open_profile(p, headless=False)
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await _wait_for_user_login(page, url, login_timeout_s)
            await _wait_until_settled(page)
            await _scroll_to_bottom(page)
            return await page.content()
        finally:
            await context.close()


def _extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "No title found"
    if soup.body:
        for irrelevant in soup.body(["script", "style", "img", "input"]):
            irrelevant.decompose()
        text = soup.body.get_text(separator="\n", strip=True)
    else:
        text = ""
    return (title + "\n\n" + text)


def fetch_website_contents(url, render_js=True, interactive=True, login_timeout_s=300):
    """
    Return the title and full text contents of the website at the given url, including
    client-rendered content.

    render_js: run the page in a real browser so client-rendered content is included.
    interactive: if the page is behind a login, open a visible browser and wait for the user to log in.
        The session is kept in PROFILE_DIR, so later calls run headless without asking again.
    login_timeout_s: how long to wait for the user to log in.
    """
    if not render_js:
        return _extract_text(_fetch_static_html(url))
    return _extract_text(_run_in_browser_thread(_fetch_rendered_html, url, interactive, login_timeout_s))
