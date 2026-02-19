"""
Podcast Agent - 메인 오케스트레이터

매일 아침 06:00에 실행하여:
1. Research Agent: YouTube 채널에서 최근 영상 URL 수집
2. NotebookLM Agent: 소스 추가 + 오디오 개요(팟캐스트) 생성

사용법:
    python main.py --now         # 즉시 1회 실행
    python main.py --loop        # 매일 06:00에 반복 실행
    python main.py --visible     # 브라우저를 표시하며 실행 (디버깅용)
"""

import sys
import time
import json
import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

# Windows 콘솔 인코딩 문제 방지 (cp949 → utf-8)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# .env 파일 로드 (로컬 환경 변수 설정)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # python-dotenv가 없으면 무시

# 같은 디렉토리의 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent))
import research_agent
from notebooklm_agent import NotebookLMAgent
from gmail_notifier import send_gmail_notification

# 스케줄 시간 설정 (24시간 형식)
SCHEDULE_HOUR = 6
SCHEDULE_MINUTE = 0


def run_once(headless: bool = True):
    """단일 실행: 영상 URL 수집 → NotebookLM 오디오 개요 생성"""
    print(f"\n{'=' * 60}")
    print(f"🎙️ 팟캐스트 에이전트 — NotebookLM 오디오 개요 자동 생성")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}\n")

    # ── Phase 1: Research ──
    print("📡 [Phase 1] Research Agent — 최근 영상 URL 수집")
    try:
        videos = research_agent.get_recent_video_urls()
    except Exception as e:
        print(f"❌ Research Agent 실패: {e}")
        return False

    if not videos:
        print("ℹ️ 최근 24시간 내 새 영상이 없습니다.")
        print("워크플로우 완료 (팟캐스트 생성 생략)")
        return True

    print(f"\n📊 수집 결과: {len(videos)}개 영상")
    for v in videos:
        print(f"  📹 [{v.get('channel', '')}] {v['title']}")

    # 영상 목록 저장
    output_dir = Path(__file__).parent
    with open(output_dir / "recent_videos.json", "w", encoding="utf-8") as f:
        json.dump(videos, f, indent=2, ensure_ascii=False)

    video_urls = [v["url"] for v in videos]

    # ── Phase 2: NotebookLM ──
    print(f"\n🎙️ [Phase 2] NotebookLM Agent — 소스 추가 + 오디오 개요 생성")
    agent = NotebookLMAgent(
        notebook_name="Daily new",
        headless=headless,
    )

    # 전체 워크플로우 실행
    # (노트북 재생성 -> 소스 추가 -> 오디오 생성 준비)
    result = agent.run(video_urls)

    # ── 결과 보고 ──
    print(f"\n{'=' * 60}")
    
    # 이메일 본문 생성
    video_list_str = "\n".join([f"- {v['title']} ({v['channel']})" for v in videos])
    
    if result["success"]:
        print(f"✅ 팟캐스트 준비 완료!")
        print(f"📎 소스 추가: {result['sources_added']}/{len(video_urls)}개")
        print(f"🎙️ 오디오 개요: {'준비 완료 (브라우저 확인 필요)' if result['audio_generated'] else '실패'}")
        print(f"🔗 노트북: {result.get('notebook_url', 'N/A')}")
        
        # Gmail 알림 (성공)
        subject = f"NotebookLM 소스 추가 완료 ({len(video_urls)}개)"
        body = (
             f"✅ [성공] 총 {len(video_urls)}개의 영상 소스가 추가되었습니다.\n\n"
             f"<영상 목록>\n{video_list_str}\n\n"
             f"👉 NotebookLM에 접속하여 '생성' 버튼을 눌러주세요."
        )
        send_gmail_notification(subject, body, success=True)
        
    else:
        print(f"⚠️ 팟캐스트 준비 실패")
        print(f"📎 소스 추가: {result['sources_added']}/{len(video_urls)}개")
        print(f"🎙️ 오디오 개요: {'준비됨' if result['audio_generated'] else '미생성'}")
        
        # Gmail 알림 (실패)
        subject = "NotebookLM 작업 실패"
        body = (
            f"⚠️ [실패] 작업을 완료하지 못했습니다.\n"
            f"- 소스 추가: {result['sources_added']}/{len(video_urls)}\n"
            f"- 오디오 준비: {'성공' if result['audio_generated'] else '실패'}"
        )
        send_gmail_notification(subject, body, success=False)
        
    print(f"{'=' * 60}")

    # 결과 저장
    result_path = output_dir / f"result_{datetime.now().strftime('%Y%m%d')}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result["success"]


def run_loop(headless: bool = True):
    """매일 06:00에 반복 실행"""
    print(f"🔄 팟캐스트 에이전트 — 매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} 자동 실행 모드")
    print(f"   종료: Ctrl+C\n")

    while True:
        now = datetime.now()

        # 다음 실행 시각 계산
        target = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        wait_hours = wait_seconds / 3600

        print(f"⏳ 다음 실행: {target.strftime('%Y-%m-%d %H:%M')} ({wait_hours:.1f}시간 후)")

        # 대기 (1분 단위 체크)
        while datetime.now() < target:
            time.sleep(60)

        # 실행
        try:
            success = run_once(headless=headless)
            status = "성공 ✅" if success else "실패 ⚠️"
            print(f"{datetime.now().strftime('%Y-%m-%d')} 실행 {status}")
        except Exception as e:
            print(f"❌ 실행 중 오류: {e}")

        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="팟캐스트 에이전트 — NotebookLM 오디오 개요 자동 생성")
    parser.add_argument("--now", action="store_true", help="즉시 1회 실행")
    parser.add_argument("--loop", action="store_true", help=f"매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}에 반복 실행")
    parser.add_argument("--visible", action="store_true", help="브라우저를 표시하며 실행 (디버깅)")
    args = parser.parse_args()

    headless = not args.visible

    if args.now:
        success = run_once(headless=headless)
        sys.exit(0 if success else 1)
    elif args.loop:
        try:
            run_loop(headless=headless)
        except KeyboardInterrupt:
            print("\n🛑 에이전트 종료")
    else:
        print("ℹ️ 옵션 없이 실행 — 즉시 1회 실행합니다")
        print("   --loop: 매일 자동 반복 / --visible: 브라우저 표시\n")
        success = run_once(headless=headless)
        sys.exit(0 if success else 1)
