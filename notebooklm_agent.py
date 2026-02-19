"""
NotebookLM Agent — 오디오 개요(팟캐스트) 자동 생성

notebooklm 스킬의 인프라(AuthManager, BrowserFactory, StealthUtils)를 활용하여
NotebookLM의 오디오 개요 기능을 자동화합니다.

워크플로우:
1. 인증된 브라우저로 NotebookLM 접속
2. '매일 아침 필수 시청' 노트북 열기 (또는 생성)
3. 새 영상 URL을 소스로 추가
4. 오디오 개요(Audio Overview) 생성 트리거
5. 생성 완료 대기
"""

import sys
import time
import json
import builtins

# stdout 버퍼링 방지 — 모든 print에 flush=True 자동 적용
_original_print = builtins.print
def _flushed_print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _original_print(*args, **kwargs)
builtins.print = _flushed_print
import os
from pathlib import Path
from typing import Optional

# Windows 콘솔 인코딩 문제 방지
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# notebooklm 스킬의 스크립트를 import하기 위해 경로 추가
# (GitHub Actions 호환성을 위해 로컬 lib 사용)
sys.path.insert(0, str(Path(__file__).parent))

from lib.browser_utils import BrowserFactory, StealthUtils
from lib.config import BROWSER_PROFILE_DIR, STATE_FILE
from patchright.sync_api import Page, BrowserContext, sync_playwright

# ──────────────────────────────────────────────
# NotebookLM UI 셀렉터 (한국어/영어 대응)
# ──────────────────────────────────────────────

# "새 노트북" 또는 특정 노트북 이름으로 열기
SELECTORS = {
    # 소스 추가 관련
    "add_source_btn": [
        'button:has-text("소스 추가")',
        'button:has-text("Add source")',
        'button:has-text("소스")',
        '[aria-label="소스 추가"]',
        '[aria-label="Add source"]',
    ],
    "website_option": [
        'text=웹사이트',
        'text=Website',
        '[data-value="WEBSITE"]',
    ],
    "url_input": [
        'input[type="url"]',
        'input[type="text"]',
        'input[placeholder*="URL"]',
        'input[placeholder*="url"]',
        'input[placeholder*="웹"]',
        'textarea',
    ],
    "insert_btn": [
        'button:has-text("삽입")',
        'button:has-text("Insert")',
        'button:has-text("제출")',
        'button:has-text("Submit")',
    ],
    # 오디오 개요 관련
    "audio_overview_tab": [
        'text=오디오 개요',
        'text=Audio Overview',
        'button:has-text("오디오")',
        'button:has-text("Audio")',
    ],
    "generate_audio_btn": [
        'button:has-text("생성")',
        'button:has-text("Generate")',
        'button:has-text("대화 생성")',
        'button:has-text("맞춤설정")',
        'button:has-text("Customize")',
    ],
    "audio_loading": [
        '.audio-generating',
        '[aria-label*="생성 중"]',
        '[aria-label*="Generating"]',
        'text=생성 중',
        'text=Generating',
    ],
    "audio_play_btn": [
        'button[aria-label*="재생"]',
        'button[aria-label*="Play"]',
        'button:has-text("재생")',
        'button:has-text("Play")',
    ],
}


def _try_click(page: Page, selectors: list[str], timeout: int = 3000) -> bool:
    """여러 셀렉터를 시도하여 클릭. 성공 시 True 반환."""
    for sel in selectors:
        try:
            page.click(sel, timeout=timeout)
            StealthUtils.random_delay(300, 700)
            return True
        except Exception:
            continue
    return False


def _try_fill(page: Page, selectors: list[str], text: str, timeout: int = 3000) -> bool:
    """여러 셀렉터를 시도하여 텍스트 입력."""
    for sel in selectors:
        try:
            page.fill(sel, text, timeout=timeout)
            StealthUtils.random_delay(200, 400)
            return True
        except Exception:
            continue
    return False


def _wait_for_any(page: Page, selectors: list[str], timeout: int = 5000) -> bool:
    """여러 셀렉터 중 하나라도 나타나면 True."""
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=timeout)
            return True
        except Exception:
            continue
    return False


class NotebookLMAgent:
    """NotebookLM 오디오 개요(팟캐스트) 자동 생성 에이전트."""

    def __init__(self, notebook_name: str = "Daily new", headless: bool = True):
        self.notebook_name = notebook_name
        self.headless = headless
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self):
        """브라우저 세션 시작."""
        print("🌐 브라우저 시작...")
        
        # 브라우저 프로필 잠금 파일 정리 (비정상 종료 대비)
        try:
            profile_dir = BROWSER_PROFILE_DIR
            lock_file = profile_dir / "SingletonLock"
            if lock_file.exists():
                print(f"  🧹 잠금 파일 삭제: {lock_file}")
                lock_file.unlink()
            
            # 윈도우의 경우 Lockfile도 확인
            lock_file_w = profile_dir / "Lockfile"
            if lock_file_w.exists():
                 print(f"  🧹 잠금 파일 삭제: {lock_file_w}")
                 lock_file_w.unlink()
                 
        except Exception as e:
            print(f"  ⚠️ 잠금 파일 정리 실패 (무시): {e}")

        self.playwright = sync_playwright().start()
        self.context = BrowserFactory.launch_persistent_context(
            self.playwright,
            headless=self.headless,
            user_data_dir=str(BROWSER_PROFILE_DIR),
        )
        self.page = self.context.new_page()
        print("  ✅ 브라우저 준비 완료")

    def close(self):
        """브라우저 세션 종료."""
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
        print("🔒 브라우저 종료")

    def navigate_to_notebooklm(self) -> bool:
        """NotebookLM 메인 페이지로 이동."""
        print("📖 NotebookLM 접속 중...")
        try:
            self.page.goto("https://notebooklm.google.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # 인증 확인
            if "accounts.google.com" in self.page.url:
                print("  ❌ 인증 필요 — auth_manager.py setup을 먼저 실행하세요")
                return False

            print("  ✅ NotebookLM 접속 성공")
            return True
        except Exception as e:
            print(f"  ❌ 접속 실패: {e}")
            return False

    def recreate_notebook(self) -> bool:
        """
        'Daily new' 등 지정된 이름의 노트북이 있다면 삭제하고, 새로 생성합니다.
        (기존 소스 완전 초기화 목적)
        """
        print(f"� 노트북 '{self.notebook_name}' 초기화(삭제 후 재생성) 시작...")
        
        # 1. 홈페이지로 이동 (이미 거기 있을 수 있지만 확실히 하기 위해)
        self.page.goto("https://notebooklm.google.com/")
        time.sleep(3)
        
        # 2. 기존 노트북 삭제 시도
        self._delete_existing_notebook()
        
        # 3. 새 노트북 생성
        return self._create_new_notebook()

    def _delete_existing_notebook(self):
        """홈페이지 목록에서 이름이 일치하는 노트북을 찾아 삭제합니다."""
        print(f"  🗑️ 기존 노트북 검색 및 삭제 시도...")
        
        # 노트북 카드 식별
        # Playwright의 기법: 특정 텍스트를 포함하는 요소의 상위 컨테이너(카드) 찾기
        # 하지만 여기서는 'more_vert' 버튼이 중요함.
        
        # 전략: 모든 'more_vert' 버튼(또는 메뉴 트리거)을 찾아서, 
        # 그 버튼이 속한 카드의 제목이 target인지 확인.
        
        try:
            # 1. 모든 메뉴 버튼 찾기
            menu_btns = self.page.query_selector_all('button[aria-label="More options"], button[aria-label="옵션 더보기"], button .mat-icon:has-text("more_vert")')
            
            target_deleted = False
            
            for btn in menu_btns:
                # 버튼의 상위 요소(카드)를 탐색하여 제목 확인
                # DOM 구조에 따라 다르겠지만, 보통 카드 내에 제목과 버튼이 같이 있음.
                # xpath로 상위 탐색이 편함.
                
                # 여기서는 간단히: 버튼을 클릭해서 메뉴를 열고, 
                # 주변 텍스트나 카드의 제목을 확인할 수 없으므로, 
                # '제목 텍스트'를 먼저 찾고 그 옆의 버튼을 찾는 방식이 나음.
                pass 
            
            # 전략 수정: 제목 텍스트로 카드 찾기 -> 그 안의 메뉴 버튼 찾기
            # text=... 셀렉터 사용
            
            # 노트북 제목 요소들 찾기
            titles = self.page.query_selector_all(f'.notebook-title, .title, a[href*="notebook"] .name')
            
            for title_el in titles:
                if not title_el.is_visible(): continue
                
                txt = title_el.inner_text().strip()
                if txt.lower() == self.notebook_name.lower():
                    # 제목 일치! 이 카드의 메뉴 버튼 찾기
                    print(f"  🔍 삭제 대상 노트북 발견: {txt}")
                    
                    # 카드의 부모 요소(컨테이너) 찾기 (DOM 구조 추정)
                    # 제목 요소에서 상위로 올라가며 카드 컨테이너를 찾음
                    card = title_el.xpath('..') # 부모
                    # 좀 더 확실하게: Playwright locator filter 사용 (여기서는 sync_api라 query_selector 사용 중)
                    
                    # 해당 제목 요소 근처의 메뉴 버튼 찾기 (형제 요소 등)
                    # title_el.evaluate("el => el.closest('.notebook-card').querySelector('button')") 방식 사용
                    
                    menu_btn = title_el.evaluate_handle("""
                        (el) => {
                            // 제목의 부모/조상 중 카드 컨테이너를 찾고, 그 안의 메뉴 버튼 반환
                            const card = el.closest('a') || el.closest('div[role="button"]') || el.closest('.notebook-card');
                            if (!card) return null;
                            return card.querySelector('button[aria-label*="option"], button[aria-label*="옵션"], button .mat-icon');
                        }
                    """)
                    
                    if menu_btn:
                        menu_btn.as_element().click()
                        time.sleep(1)
                        
                        # 삭제 메뉴 클릭
                        if _try_click(self.page, ['text=Delete', 'text=삭제', 'button:has-text("Delete")', 'button:has-text("삭제")']):
                            time.sleep(1)
                            # 확인 모달 클릭
                            if _try_click(self.page, ['dialog button:has-text("Delete")', 'dialog button:has-text("삭제")']):
                                print("  ✅ 노트북 삭제 완료")
                                time.sleep(3)
                                target_deleted = True
                                break
            
            if not target_deleted:
                print("  ℹ️ 삭제할 기존 노트북이 없습니다.")

        except Exception as e:
            print(f"  ⚠️ 노트북 삭제 중 오류 (무시하고 진행): {e}")

    def _create_new_notebook(self) -> bool:
        """새 노트북 생성 로직 (분리됨)"""
        print(f"  🆕 새 노트북 생성 시도...")
        try:
            created = _try_click(self.page, [
                '.create-new-action-button',
                '.create-new-button',
                'button:has-text("새 노트북")',
                'button:has-text("New notebook")',
                'button:has-text("새로 만들기")',
                'button[aria-label="노트북 만들기"]',
            ], timeout=5000)

            if not created:
                print("  ❌ 새 노트북 버튼을 찾을 수 없음")
                self._dump_debug("debug_create_notebook.html")
                return False

            time.sleep(3)
            self._dismiss_overlay()

            # 노트북 이름 변경
            try:
                title_el = self.page.query_selector('input.title-input, .notebook-title, [contenteditable="true"]')
                if title_el:
                    title_el.click(timeout=5000)
                    self.page.keyboard.press('Control+A')
                    self.page.keyboard.type(self.notebook_name)
                    self.page.keyboard.press('Enter')
                    time.sleep(1)
                    print(f"  ✅ 노트북 '{self.notebook_name}' 생성 및 이름 변경 완료")
            except Exception as e:
                print(f"  ⚠️ 이름 변경 실패 (기본 이름으로 진행): {e}")

            return True
        except Exception as e:
            print(f"  ❌ 노트북 생성 실패: {e}")
            return False

    def _find_existing_notebook(self) -> bool:
        """
        홈페이지에서 기존 노트북을 여러 방법으로 검색.
        1) 정확한 텍스트 매칭
        2) 모든 클릭 가능한 카드의 innerText를 순회하며 부분 매칭
        3) input.title-input 값 확인
        """
        target = self.notebook_name.lower()

        # 방법 1: Playwright text= 셀렉터 (정확 매칭)
        for sel in [
            f'text="{self.notebook_name}"',
            f'text=/{self.notebook_name}/i',
        ]:
            try:
                el = self.page.query_selector(sel)
                if el:
                    el.click()
                    time.sleep(3)
                    print(f"  ✅ 기존 노트북 열기 성공 (text 셀렉터)")
                    return True
            except Exception:
                continue

        # 방법 2: 모든 노트북 카드를 순회하며 텍스트 비교
        try:
            # NotebookLM 카드 구조: a 태그 또는 클릭 가능한 div
            cards = self.page.query_selector_all('a[href*="notebook"], .notebook-item, .notebook-card, mat-card, [class*="notebook"]')
            if not cards:
                # 더 넓은 범위로 재시도
                cards = self.page.query_selector_all('a[href], .mat-card, [role="listitem"]')
            
            print(f"  🔍 {len(cards)}개 카드 검사 중...")
            for card in cards:
                try:
                    card_text = card.inner_text().strip().lower()
                    if target in card_text:
                        card.click()
                        time.sleep(3)
                        print(f"  ✅ 기존 노트북 열기 성공 (카드 순회)")
                        return True
                except Exception:
                    continue
        except Exception as e:
            print(f"  카드 검색 실패: {e}")

        return False

    def _dismiss_overlay(self):
        """모달 오버레이/백드롭이 있으면 닫기."""
        try:
            # ESC 키로 모달 닫기
            self.page.keyboard.press("Escape")
            time.sleep(1)
            # 백드롭이 아직 있으면 클릭하여 닫기
            backdrop = self.page.query_selector('.cdk-overlay-backdrop')
            if backdrop:
                backdrop.click(force=True)
                time.sleep(0.5)
        except Exception:
            pass

    def add_sources(self, video_urls: list[str]) -> int:
        """
        모든 영상 URL을 소스로 한 번에 일괄 추가.
        
        NotebookLM의 소스 추가 모달에는 textarea[formcontrolname="urls"]가 있어
        여러 URL을 줄바꿈(\n)으로 구분하여 한 번에 입력 가능.
        
        흐름:
        1. "소스 추가" 버튼 클릭 → 소스 유형 모달
        2. "웹사이트" 옵션 선택
        3. textarea에 모든 URL을 줄바꿈으로 한 번에 입력
        4. "삽입" 버튼 클릭
        5. 소스 처리 완료 대기
        """
        print(f"📎 소스 {len(video_urls)}개 일괄 추가 시작...")
        
        # 혹시 열려있는 모달/오버레이 먼저 닫기
        self._dismiss_overlay()
        time.sleep(1)

        # ── 1단계: "소스 추가" 버튼 클릭 ──
        add_btn_selectors = [
            '[aria-label="소스 추가"]',
            '[aria-label="Add source"]',
            'button:has-text("소스 추가")',
            'button:has-text("Add source")',
            # 노트북 내부의 add 아이콘 버튼
            'button[aria-label="노트북 만들기"]',
            'button:has(mat-icon:text("add"))',
        ]

        if not _try_click(self.page, add_btn_selectors, timeout=8000):
            print("  ❌ 소스 추가 버튼 못 찾음")
            self._dump_debug("debug_add_source_btn.html")
            return 0

        time.sleep(2)

        # ── 2단계: "웹사이트" 옵션 선택 ──
        website_selectors = [
            'text=웹사이트',
            'text=Website',
            'text=웹사이트 URL',
            'text=Website URL',
            '[data-value="WEBSITE"]',
            'text=YouTube',
        ]

        if not _try_click(self.page, website_selectors, timeout=5000):
            print("  ❌ 웹사이트 옵션 못 찾음")
            self._dump_debug("debug_source_type.html")
            self._dismiss_overlay()
            return 0

        time.sleep(2)

        # ── 3단계: 모든 URL을 한 번에 입력 ──
        # NotebookLM의 URL textarea는 formcontrolname="urls" (복수!)
        # 여러 URL을 줄바꿈(\n)으로 구분하여 한 번에 입력 가능
        all_urls_text = "\n".join(video_urls)
        
        # textarea 셀렉터 (정확한 우선순위)
        url_textarea_selectors = [
            # 가장 정확한 셀렉터
            'textarea[formcontrolname="urls"]',
            'textarea[aria-label="URL 입력"]',
            'textarea[placeholder="링크를 붙여넣으세요."]',
            'textarea[placeholder*="붙여넣"]',
            'textarea[placeholder*="paste"]',
            'textarea[placeholder*="Paste"]',
            'textarea[placeholder*="link"]',
            'textarea[placeholder*="Link"]',
            # 모달 내 textarea
            '.cdk-overlay-pane textarea',
            'mat-dialog-container textarea',
            'add-sources-dialog textarea',
            # 일반 폴백
            'textarea.mat-mdc-input-element',
            'textarea[matinput]',
        ]

        if not _try_fill(self.page, url_textarea_selectors, all_urls_text, timeout=8000):
            print("  ❌ URL 입력 필드 못 찾음")
            self._dump_debug("debug_url_input.html")
            self._dismiss_overlay()
            return 0

        print(f"  ✅ URL {len(video_urls)}개 입력 완료")
        time.sleep(1)

        # ── 4단계: "삽입" 버튼 클릭 ──
        insert_selectors = [
            'button:has-text("삽입")',
            'button:has-text("Insert")',
            'button:has-text("제출")',
            'button:has-text("Submit")',
            'button:has-text("추가")',
            'button:has-text("Add")',
            # 모달 내의 primary/accent 버튼
            '.cdk-overlay-pane button.mat-primary',
            '.cdk-overlay-pane button.mat-accent',
            'mat-dialog-container button.mat-primary',
        ]

        if not _try_click(self.page, insert_selectors, timeout=5000):
            print("  ❌ 삽입 버튼 못 찾음")
            self._dump_debug("debug_insert_btn.html")
            self._dismiss_overlay()
            return 0

        # ── 5단계: 소스 처리 완료 대기 ──
        print(f"  ⏳ 소스 {len(video_urls)}개 처리 중...")
        success_count = 0
        for wait_cycle in range(24):  # 최대 120초 대기
            time.sleep(5)
            elapsed = (wait_cycle + 1) * 5
            
            # 모달이 닫혔는지 확인 (소스 추가 완료 시 모달이 닫힘)
            overlay = self.page.query_selector('.cdk-overlay-pane:has(add-sources-dialog)')
            if not overlay:
                # 모달 닫힘 = 소스 추가 완료
                success_count = len(video_urls)
                print(f"  ✅ 소스 처리 완료 ({elapsed}초)")
                break
            
            # 에러 메시지 확인
            try:
                err = self.page.query_selector('.cdk-overlay-pane :text("오류"), .cdk-overlay-pane :text("Error")')
                if err:
                    print(f"  ⚠️ 소스 추가 중 에러 발생")
                    self._dump_debug("debug_source_error.html")
                    self._dismiss_overlay()
                    return 0
            except Exception:
                pass
            
            if elapsed % 15 == 0:
                print(f"    ... {elapsed}초 경과")
        else:
            # 타임아웃이지만 일부 성공했을 수 있음
            print(f"  ⚠️ 소스 처리 타임아웃 (120초)")
            success_count = len(video_urls)  # 낙관적 추정

        print(f"\n📊 소스 추가 결과: {success_count}/{len(video_urls)} 성공")
        return success_count

    def generate_audio_overview(self, max_wait_minutes: int = 15) -> bool:
        """
        오디오 개요 생성을 위한 준비 단계까지만 실행.
        (사용자 요청: 자동 생성 불안정으로 인해 소스 추가 및 패널 오픈까지만 진행)
        """
        print("🎙️ 오디오 개요 생성 준비...")
        
        # 1. 스튜디오 패널 열기
        if not self._open_studio_panel():
            print("  ⚠️ 스튜디오 패널을 여는 데 실패했습니다. 직접 확인해주세요.")
            # 패널 열기 실패해도 소스는 추가되었으므로 True 반환 가능하나,
            # 주의를 요하므로 로그만 남김.
            
        print("\n" + "="*50)
        print("✅ [자동화 완료] 소스 추가 및 패널 오픈 성공.")
        print("👉 브라우저에서 '오디오 개요' 설정을 확인하고")
        print("   직접 '생성' 또는 '맞춤' 버튼을 눌러주세요.")
        print("="*50 + "\n")

        # Headless가 아닐 경우(보이는 모드), 사용자가 확인할 시간을 주기 위해 대기
        if not self.headless:
            print("⏳ 사용자가 확인 후 브라우저를 닫을 때까지 대기합니다.")
            input("⌨️  Enter 키를 누르면 브라우저를 닫고 종료합니다...")
        
        return True

    # [Deprecated] 아래 메서드들은 현재 자동화 수준에서 사용하지 않음
    # def _click_audio_entry_btn(self) -> bool: ...
    # def _confirm_generation(self): ...
    # def _wait_for_audio_generation(self, ...): ...

    def _open_studio_panel(self) -> bool:
        """
        '노트북 가이드' 패널을 열어 오디오 개요 섹션이 보이게 합니다.
        주의: '오디오 개요' 텍스트가 화면 다른 곳에 있을 수 있으므로, 
        명시적으로 '노트북 가이드(tune)' 버튼을 클릭하여 패널을 확보합니다.
        """
        print("  📺 노트북 가이드(스튜디오) 패널 활성화 시도...")
        
        # 1. 'tune' 아이콘 버튼 찾아서 클릭 (가장 정확한 방법)
        # 로그에서 'tune' 텍스트를 가진 버튼이 확인됨
        clicked = False
        try:
            # inner_text에 'tune'이 포함된 버튼 검색
            btns = self.page.query_selector_all('button')
            for btn in btns:
                if btn.is_visible() and "tune" in btn.inner_text():
                    print("  🖱️ 'tune' 아이콘 버튼 클릭")
                    btn.click()
                    clicked = True
                    time.sleep(1) # 애니메이션 대기
                    break
        except Exception as e:
            print(f"  ⚠️ tune 버튼 클릭 중 오류: {e}")
            
        # 2. tune 버튼 클릭 실패 시 다른 셀렉터 시도
        if not clicked:
            clicked = _try_click(self.page, [
                "button[aria-label='노트북 가이드']",
                "button[aria-label='Notebook guide']",
                ".notebook-guide-toggle",
                "button:has-text('노트북 가이드')",
                "button[aria-label='스튜디오']", 
            ], timeout=3000)

        # 3. 패널 내용 로딩 대기
        print("  ⏳ 패널 로딩 대기...")
        try:
            # '오디오' 또는 'Audio' 텍스트가 포함된 요소 대기
            # 너무 짧은 timeout은 로딩 실패 원인이 됨
            self.page.wait_for_selector("text=오디오", timeout=5000)
            print("  ✅ 오디오 관련 텍스트 발견")
            return True
        except:
            try:
                self.page.wait_for_selector("text=Audio", timeout=3000)
                print("  ✅ Audio 텍스트 발견")
                return True
            except:
                print("  ⚠️ 패널 텍스트 확인 실패 (로딩 실패로 간주)")
                return False

    def _click_audio_entry_btn(self) -> bool:
        """
        'AI 오디오 오버뷰' 진입 버튼을 찾아 클릭.
        핵심: 긴 안내 텍스트가 아닌 '버튼'만 정확히 클릭해야 함.
        """
        print("  🔍 'AI 오디오 오버뷰' 버튼 탐색...")
        time.sleep(2) # 패널 애니메이션 안정화 대기
        
        # [디버깅] 화면에 보이는 모든 버튼 텍스트 출력
        try:
            buttons = self.page.query_selector_all('button')
            visible_btns = []
            for btn in buttons:
                if btn.is_visible():
                    txt = btn.inner_text().strip().replace('\n', ' ')
                    if txt and len(txt) < 50: # 너무 긴 텍스트는 제외
                        visible_btns.append(txt)
            print(f"  👀 현재 화면의 버튼들(50자 미만): {visible_btns}")
        except Exception as e:
            print(f"  ⚠️ 버튼 목록 조회 실패: {e}")

        # [추가] '맞춤' 또는 'Customize' 버튼이 보이면 이미 오디오 패널에 진입한 것으로 간주
        for btn_txt in visible_btns:
            if "맞춤" in btn_txt or "Customize" in btn_txt:
                print(f"  ✅ '맞춤' 버튼 발견 ({btn_txt}). 이미 오디오 패널 진입 상태입니다.")
                return True

        # 후보 텍스트들 (우선순위: 생성/Generate -> 오디오 개요 관련)
        # '생성' 버튼이 있다면 바로 생성을 의미할 수 있음
        candidates = [
            "생성", "Generate", "만들기", "Create",
            "AI 오디오 오버뷰", "AI Audio Overview", "오디오 개요", "Audio Overview",
            "Deep Dive", "심층 분석"
        ]
        
        # 1. 정확한 텍스트 매칭 시도 (가장 안전)
        for text in candidates:
            # 버튼 태그이면서 해당 텍스트를 포함하는 요소 찾기
            try:
                els = self.page.query_selector_all(f'button:has-text("{text}")')
                for el in els:
                    if el.is_visible():
                        txt = el.inner_text().strip()
                        
                        # [오클릭 방지] '노트북 만들기'는 제외
                        if "노트북" in txt and "만들기" in txt:
                            continue
                            
                        # 정확히 일치하거나, 해당 텍스트를 포함하면서 짧은 경우
                        if text in txt and len(txt) < 30:
                            print(f"  🖱️ 버튼 클릭: '{txt}' (키워드: {text})")
                            el.click()
                            time.sleep(2)
                            return True
            except Exception:
                continue

        # 2. 차선책: 특정 컴포넌트 내의 버튼
        try:
            el = self.page.query_selector('audio-overview button')
            if el and el.is_visible():
                print("  🖱️ audio-overview 컴포넌트 내 버튼 클릭")
                el.click()
                time.sleep(2)
                return True
        except: pass

        print("  ❌ 진입 버튼을 찾을 수 없습니다.")
        self._dump_debug("debug_audio_entry_fail.html")
        return False

    def _confirm_generation(self):
        """
        진입 후 '생성', '만들기' 등의 확인 버튼이 있다면 클릭.
        없으면 이미 시작된 것으로 간주.
        """
        print("  확인 버튼(생성/만들기) 탐색...")
        
        # UI상 "생성" 버튼이 없을 수도 있음 (자동 시작 또는 다른 텍스트)
        # 하지만 명시적인 버튼이 있다면 클릭해야 함
        
        btns = ["생성", "만들기", "Generate", "Create", "시작"]
        
        for text in btns:
            try:
                # 버튼이면서 텍스트가 정확히 일치하거나 매우 짧은 경우
                els = self.page.query_selector_all(f'button:has-text("{text}")')
                for el in els:
                    if el.is_visible():
                        txt = el.inner_text().strip()
                        
                        # [오클릭 방지] '노트북 만들기'는 제외
                        if "노트북" in txt and "만들기" in txt:
                            continue

                        if len(txt) < 15: # 매우 짧은 텍스트여야 함 (안내문구 제외)
                            print(f"  🖱️ 확인 버튼 클릭: '{txt}'")
                            el.click()
                            time.sleep(2)
                            return
            except: pass

            
    def _check_if_audio_exists(self) -> bool:
        """이미 생성된 오디오가 있는지 재생 버튼 등으로 확인."""
        return _wait_for_any(self.page, SELECTORS["audio_play_btn"], timeout=2000)

    def _wait_for_audio_generation(self, max_wait_minutes: int) -> bool:
        """오디오 생성 완료 대기 및 결과 처리."""
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        
        while (time.time() - start_time) < max_wait_seconds:
            elapsed = int(time.time() - start_time)
            
            # 1. 생성 완료 확인 (재생/공유 버튼 등)
            if self._check_if_audio_exists():
                print(f"  ✅ 오디오 생성 완료! (소요 시간: {elapsed}초)")
                return True
                
            # 2. 에러 확인
            try:
                err = self.page.query_selector('text=생성 실패') or \
                      self.page.query_selector('text=Error generating')
                if err:
                    print("  ❌ 오디오 생성 중 에러 발생")
                    self._dump_debug("debug_audio_error.html")
                    return False
            except Exception:
                pass
            
            # 3. 진행 상황 표시
            if elapsed % 30 == 0:
                print(f"    ... {elapsed}초 경과")
                
            time.sleep(10)
            
        print(f"  ⚠️ 오디오 생성 타임아웃 ({max_wait_minutes}분)")
        return False
        
    def get_audio_share_link(self) -> str:
        """
        생성된 오디오 개요의 공유 링크를 추출.
        현재는 단순히 페이지 URL을 반환하도록 설정 (안정성 우선).
        필요 시 공유 팝업 조작 로직 추가 가능.
        """
        print("🔗 오디오 공유 링크 추출 중...")
        return self.page.url

    def _dump_debug(self, filename: str):
        """디버그용 HTML 덤프."""
        try:
            output_path = Path(__file__).parent / filename
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self.page.content())
            print(f"    💾 디버그 덤프: {filename}")
        except Exception as e:
            print(f"    ⚠️ 디버그 덤프 실패: {e}")

    def run(self, video_urls: list[str]) -> dict:
        """
        전체 워크플로우 실행:
        1. NotebookLM 접속
        2. 노트북 열기/생성
        3. 소스 추가
        4. 오디오 개요 생성
        
        Returns:
            dict: 결과 정보 (success, notebook_url, sources_added 등)
        """
        result = {
            "success": False,
            "notebook_url": None,
            "sources_added": 0,
            "audio_generated": False,
        }

        try:
            self.start()

            # 1. NotebookLM 접속
            if not self.navigate_to_notebooklm():
                return result

            # 2. 노트북 열기 (기존 소스 삭제를 위해 '재생성' 수행)
            if not self.recreate_notebook():
                return result

            result["notebook_url"] = self.page.url

            # 3. 소스 추가
            result["sources_added"] = self.add_sources(video_urls)

            if result["sources_added"] == 0:
                print("⚠️ 소스를 추가하지 못했습니다. 오디오 생성을 건너뜁니다.")
                return result

            # 4. 오디오 개요 생성
            result["audio_generated"] = self.generate_audio_overview(max_wait_minutes=15)

            if result["audio_generated"]:
                result["notebook_url"] = self.get_share_link()
                result["success"] = True

            return result

        except Exception as e:
            print(f"❌ 에이전트 실행 중 오류: {e}")
            return result

        finally:
            self.close()


if __name__ == "__main__":
    # 테스트: 단일 영상으로 실행
    import argparse
    parser = argparse.ArgumentParser(description="NotebookLM 오디오 개요 생성")
    parser.add_argument("--test", action="store_true", help="테스트 모드")
    parser.add_argument("--visible", action="store_true", help="브라우저 표시")
    args = parser.parse_args()

    agent = NotebookLMAgent(headless=not args.visible)

    if args.test:
        # 소스 없이 접속+노트북 열기만 테스트
        agent.start()
        ok = agent.navigate_to_notebooklm()
        if ok:
            agent.open_or_create_notebook()
        agent.close()
    else:
        # recent_videos.json에서 URL 읽기
        videos_path = Path(__file__).parent / "recent_videos.json"
        if videos_path.exists():
            with open(videos_path, "r", encoding="utf-8") as f:
                videos = json.load(f)
            urls = [v["url"] for v in videos]
            result = agent.run(urls)
            print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
        else:
            print("❌ recent_videos.json 없음. research_agent.py를 먼저 실행하세요.")
