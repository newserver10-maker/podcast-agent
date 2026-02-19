import sys
import json
import base64
import os
from pathlib import Path

# 로컬 라이브러리 참조
sys.path.insert(0, str(Path(__file__).parent))
try:
    from lib.config import STATE_FILE, BROWSER_STATE_DIR
except ImportError:
    # 로컬 테스트를 위한 폴백 (skills 폴더가 있는 경우)
    print("⚠️ lib.config를 찾을 수 없어 skills 디렉토리 경로를 시도합니다.", file=sys.stderr)
    SKILL_DIR = Path("e:/Anti gravity/skills/notebooklm")
    BROWSER_STATE_DIR = SKILL_DIR / "data" / "browser_state"
    STATE_FILE = BROWSER_STATE_DIR / "state.json"


def export_state_json() -> str:
    """state.json(쿠키)을 base64로 인코딩하여 반환."""
    if not STATE_FILE.exists():
        print(f"❌ state.json을 찾을 수 없습니다: {STATE_FILE}", file=sys.stderr)
        print("   먼저 로컬 브라우저로 로그인하여 쿠키를 생성하세요.", file=sys.stderr)
        sys.exit(1)

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    # 쿠키 개수 확인
    cookies = state.get("cookies", [])
    print(f"📦 쿠키 {len(cookies)}개 발견", file=sys.stderr)

    # base64 인코딩
    state_bytes = json.dumps(state).encode("utf-8")
    b64 = base64.b64encode(state_bytes).decode("ascii")

    return b64


def restore_auth_from_env():
    """GitHub Secret(NOTEBOOKLM_AUTH_STATE)에서 인증 정보 복원"""
    b64_string = os.environ.get("NOTEBOOKLM_AUTH_STATE")
    if not b64_string:
        print("⚠️ 환경 변수 'NOTEBOOKLM_AUTH_STATE'가 없습니다. 인증 복원을 건너뜁니다.")
        return

    try:
        # base64 디코딩
        state_bytes = base64.b64decode(b64_string)
        state = json.loads(state_bytes)
        
        # 디렉토리 생성 (GitHub Actions 환경 등)
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            
        cookies = state.get("cookies", [])
        print(f"✅ 인증 정보 복원 완료 (쿠키 {len(cookies)}개)")
        print(f"   경로: {STATE_FILE}")
        
    except Exception as e:
        print(f"❌ 인증 정보 복원 실패: {e}")
        # 복원 실패는 치명적일 수 있으므로 stderr 출력 후 종료하지 않음 (상황에 따라 다름)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        # 복원 모드 (GitHub Actions에서 실행)
        restore_auth_from_env()
    else:
        # 내보내기 모드 (로컬에서 실행)
        try:
            b64 = export_state_json()
            print(f"✅ base64 인코딩 완료 ({len(b64)}자)", file=sys.stderr)
            print(f"\n아래 값을 GitHub Secret 'NOTEBOOKLM_AUTH_STATE'에 등록하세요:", file=sys.stderr)
            print(f"명령어: gh secret set NOTEBOOKLM_AUTH_STATE", file=sys.stderr)
            print("-" * 60, file=sys.stderr)
            print(b64) # 실제 값은 stdout으로 출력
            print("-" * 60, file=sys.stderr)
        except Exception as e:
            sys.exit(1)
