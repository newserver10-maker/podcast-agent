import json
import sys
from pathlib import Path

# lib.config에서 STATE_FILE 경로 가져오기
sys.path.insert(0, str(Path(__file__).parent))
try:
    from lib.config import STATE_FILE
except ImportError:
    STATE_FILE = Path("data/browser_state/state.json")

def import_cookies_from_json(json_content: str):
    """
    브라우저(Chrome 등)에서 내보낸 JSON 형식의 쿠키를 state.json 형식으로 변환하여 저장합니다.
    """
    try:
        cookies = json.loads(json_content)
        
        # 만약 리스트가 아니라면 에러 (보통 EditThisCookie 등은 리스트로 내보냄)
        if not isinstance(cookies, list):
            print("❌ 올바른 JSON 리스트 형식이 아닙니다.")
            return

        # NotebookLM이 기대하는 state.json 구조 생성
        # Playwright는 sameSite에 'unspecified'를 허용하지 않으므로 'None'으로 변환하거나 제거해야 합니다.
        for cookie in cookies:
            if cookie.get("sameSite") == "unspecified":
                cookie["sameSite"] = "None"
            # 번호(id) 필드가 있으면 제거 (Playwright add_cookies 스펙에 없음)
            if "id" in cookie:
                del cookie["id"]

        state = {
            "cookies": cookies,
            "origins": []
        }

        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            
        print(f"✅ 쿠키 주입 완료! ({len(cookies)}개)")
        print(f"   경로: {STATE_FILE}")
        print("\n이제 'python export_auth.py'를 실행하여 GitHub Secret용 코드를 생성하세요.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    print("--- NotebookLM Cookie Importer ---")
    print("브라우저(Chrome DevTools -> Application -> Cookies -> notebooklm.google.com)에서")
    print("전체 쿠키를 JSON 형식으로 복사하여 아래에 붙여넣어주세요.")
    print("(또는 EditThisCookie 확장프로그램으로 내보낸 JSON)")
    print("입력 후 Ctrl+Z (Windows) 또는 Ctrl+D (Mac/Linux)를 눌러 종료:")
    
    content = sys.stdin.read()
    if content.strip():
        import_cookies_from_json(content)
    else:
        print("입력된 내용이 없습니다.")
