"""
Browser Utilities for NotebookLM Skill
Handles browser launching, stealth features, and common interactions
"""

import json
import time
import random
from typing import Optional, List

from patchright.sync_api import Playwright, BrowserContext, Page
from .config import BROWSER_PROFILE_DIR, STATE_FILE, BROWSER_ARGS, USER_AGENT


class BrowserFactory:
    """Factory for creating configured browser contexts"""

    @staticmethod
    def launch_persistent_context(
        playwright: Playwright,
        headless: bool = True,
        user_data_dir: str = str(BROWSER_PROFILE_DIR)
    ) -> BrowserContext:
        """
        Launch a persistent browser context with anti-detection features
        and cookie workaround.
        """
        # Launch persistent context
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            user_agent=USER_AGENT,
            args=BROWSER_ARGS
        )

        # Cookie Workaround for Playwright bug #36139
        BrowserFactory._inject_cookies(context)
        
        return context

    @staticmethod
    def _inject_cookies(context: BrowserContext):
        """Inject cookies from state.json if available with sanitization"""
        abs_state_path = STATE_FILE.resolve()
        
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    if 'cookies' in state and len(state['cookies']) > 0:
                        # Playwright 호환성을 위한 쿠키 정규화
                        sanitized_cookies = []
                        for cookie in state['cookies']:
                            s_cookie = cookie.copy()
                            
                            # sameSite 값 정규화 (Playwright는 Strict, Lax, None만 허용)
                            ss = s_cookie.get('sameSite', '').lower()
                            if ss in ['no_restriction', 'unspecified', 'none', '']:
                                s_cookie['sameSite'] = 'None'
                            elif 'lax' in ss:
                                s_cookie['sameSite'] = 'Lax'
                            elif 'strict' in ss:
                                s_cookie['sameSite'] = 'Strict'
                            else:
                                s_cookie['sameSite'] = 'Lax' # 기본값
                            
                            # 불필요하거나 충돌을 일으키는 필드 제거
                            for field in ['id', 'storeId', 'hostOnly']:
                                if field in s_cookie:
                                    del s_cookie[field]
                                    
                            sanitized_cookies.append(s_cookie)
                            
                        context.add_cookies(sanitized_cookies)
                        print(f"  🍪 쿠키 {len(sanitized_cookies)}개 정규화 및 주입 완료")
                        print(f"     (경로: {abs_state_path})")
            except Exception as e:
                print(f"  ⚠️ 쿠키 주입 실패: {e}")
        else:
            print(f"  ℹ️ 쿠키 파일 없음 (건너뜀): {abs_state_path}")


class StealthUtils:
    """Human-like interaction utilities"""

    @staticmethod
    def random_delay(min_ms: int = 100, max_ms: int = 500):
        """Add random delay"""
        time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))

    @staticmethod
    def human_type(page: Page, selector: str, text: str, wpm_min: int = 320, wpm_max: int = 480):
        """Type with human-like speed"""
        element = page.query_selector(selector)
        if not element:
            # Try waiting if not immediately found
            try:
                element = page.wait_for_selector(selector, timeout=2000)
            except:
                pass
        
        if not element:
            print(f"Element not found for typing: {selector}")
            return

        # Click to focus
        element.click()
        
        # Type
        for char in text:
            element.type(char, delay=random.uniform(25, 75))
            if random.random() < 0.05:
                time.sleep(random.uniform(0.15, 0.4))

    @staticmethod
    def realistic_click(page: Page, selector: str):
        """Click with realistic movement"""
        element = page.query_selector(selector)
        if not element:
            return

        # Optional: Move mouse to element (simplified)
        box = element.bounding_box()
        if box:
            x = box['x'] + box['width'] / 2
            y = box['y'] + box['height'] / 2
            page.mouse.move(x, y, steps=5)

        StealthUtils.random_delay(100, 300)
        element.click()
        StealthUtils.random_delay(100, 300)
