"""
Research Agent - YouTube 채널에서 최근 영상 수집 및 자막 추출

이전 방식: Playwright로 YouTube 채널 페이지를 스크래핑 (브라우저 필요)
새로운 방식: RSS 피드 + youtube-transcript-api (브라우저 불필요)

왜 변경했는가:
- Playwright 방식은 셀렉터 변경에 취약하고, headless 모드에서 불안정
- RSS + API 방식은 순수 HTTP 호출이므로 안정적이고 빠름
"""

import json
import re
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows 콘솔 인코딩 문제 방지 (cp949 → utf-8)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

# v1.2.4: 인스턴스 기반 API
ytt_api = YouTubeTranscriptApi()

# ──────────────────────────────────────────────
# 대상 채널 설정
# channel_id는 YouTube RSS 피드에서 필요 (핸들 → ID 변환)
# ──────────────────────────────────────────────
CHANNELS = [
    {"handle": "@sosumonkey", "name": "소수몽키", "channel_id": "UCC3yfxS5qC6PCwDzetUuEWg"},
    {"handle": "@orlandocampus", "name": "올랜도 킴 미국주식", "channel_id": "UCwSSqi-s0wcH6pJbH3YPZqQ"},
    {"handle": "@buiknam_tv", "name": "부읽나TV_내집마련부터건물주까지", "channel_id": "UC2QeHNJFfuQWB4cy3M-745g"},
]

# 자막 우선순위: 한국어 > 영어
TRANSCRIPT_LANGUAGES = ["ko", "en"]

# 몇 시간 이내 영상을 "최근"으로 볼 것인지
RECENT_HOURS = 24


def resolve_channel_id(handle: str) -> str | None:
    """
    YouTube 핸들(@이름)에서 channel_id를 가져온다.
    방법: 채널 페이지 HTML에서 'channel_id' 메타 태그를 파싱.
    """
    url = f"https://www.youtube.com/{handle}"
    try:
        resp = requests.get(url, headers={"Accept-Language": "ko-KR"}, timeout=10)
        resp.raise_for_status()
        # HTML에서 channel_id 추출
        match = re.search(r'"channelId":"(UC[^"]+)"', resp.text)
        if match:
            return match.group(1)
        # externalId에서 시도 (최신 YouTube 페이지 구조)
        match = re.search(r'externalId.{0,5}(UC[a-zA-Z0-9_-]{22})', resp.text)
        if match:
            return match.group(1)
        # meta 태그에서도 시도
        match = re.search(r'<meta\s+itemprop="channelId"\s+content="(UC[^"]+)"', resp.text)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"  [WARN] 채널 ID 조회 실패 ({handle}): {e}")
    return None


def get_recent_videos_from_rss(channel_id: str, channel_name: str, hours: int = RECENT_HOURS) -> list[dict]:
    """
    YouTube RSS 피드에서 최근 N시간 이내 영상 목록을 가져온다.
    RSS 피드 URL: https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID
    """
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(feed_url)
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = []
    
    for entry in feed.entries[:10]:  # 최근 10개만 확인
        # RSS의 published 시간 파싱
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        
        if published >= cutoff:
            video_id = entry.yt_videoid
            recent.append({
                "title": entry.title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "published": published.isoformat(),
                "channel": channel_name,
            })
    
    return recent


def extract_transcript(video_id: str) -> str | None:
    """
    YouTube 영상에서 자막(transcript)을 추출한다.
    한국어 > 영어 순으로 시도.
    v1.2.4: 인스턴스 기반 fetch() 메서드 사용
    """
    try:
        transcript = ytt_api.fetch(video_id, languages=TRANSCRIPT_LANGUAGES)
        # 자막 세그먼트를 하나의 텍스트로 합침
        full_text = " ".join([snippet.text for snippet in transcript.snippets])
        return full_text
    except TranscriptsDisabled:
        print(f"    [SKIP] 자막 비활성화: {video_id}")
    except NoTranscriptFound:
        print(f"    [SKIP] 자막 없음: {video_id}")
    except VideoUnavailable:
        print(f"    [SKIP] 영상 접근 불가: {video_id}")
    except Exception as e:
        print(f"    [WARN] 자막 추출 실패: {e}")
    return None


def get_recent_videos_with_transcripts(hours: int = RECENT_HOURS) -> list[dict]:
    """
    모든 대상 채널에서 최근 영상을 수집하고, 자막을 추출한다.
    
    Returns:
        list[dict]: 각 영상의 제목, URL, 자막 텍스트 등
    """
    results = []
    
    for ch in CHANNELS:
        print(f"📡 채널 확인: {ch['name']} ({ch['handle']})")
        
        # 1. 채널 ID 조회
        channel_id = ch.get("channel_id")
        if not channel_id:
            channel_id = resolve_channel_id(ch["handle"])
            if not channel_id:
                print(f"  [ERROR] 채널 ID를 찾을 수 없음: {ch['handle']}")
                continue
            ch["channel_id"] = channel_id
            print(f"  채널 ID: {channel_id}")
        
        # 2. RSS에서 최근 영상 목록 가져오기
        videos = get_recent_videos_from_rss(channel_id, ch["name"], hours)
        print(f"  최근 {hours}시간 내 영상: {len(videos)}개")
        
        # 3. 각 영상에서 자막 추출
        for video in videos:
            print(f"  📹 {video['title']}")
            transcript = extract_transcript(video["video_id"])
            if transcript:
                video["transcript"] = transcript
                video["transcript_length"] = len(transcript)
                print(f"    ✅ 자막 추출 완료 ({len(transcript)}자)")
                results.append(video)
            else:
                print(f"    ⚠️ 자막 없이 건너뜀")
    
    return results


def get_recent_video_urls(hours: int = RECENT_HOURS) -> list[dict]:
    """
    모든 대상 채널에서 최근 영상 URL만 수집한다.
    자막 추출 없이 URL만 가져오므로 훨씬 빠르다.
    NotebookLM이 YouTube URL에서 직접 내용을 처리하므로 자막 불필요.
    
    Returns:
        list[dict]: 각 영상의 제목, URL, video_id 등
    """
    results = []
    
    for ch in CHANNELS:
        print(f"📡 채널 확인: {ch['name']} ({ch['handle']})")
        
        channel_id = ch.get("channel_id")
        if not channel_id:
            channel_id = resolve_channel_id(ch["handle"])
            if not channel_id:
                print(f"  [ERROR] 채널 ID를 찾을 수 없음: {ch['handle']}")
                continue
            ch["channel_id"] = channel_id
        
        videos = get_recent_videos_from_rss(channel_id, ch["name"], hours)
        print(f"  최근 {hours}시간 내 영상: {len(videos)}개")
        
        for video in videos:
            print(f"  📹 {video['title']}")
            results.append(video)
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("🔬 Research Agent 시작")
    print("=" * 60)
    
    # URL만 수집 (기본 모드 — NotebookLM용)
    videos = get_recent_video_urls()
    
    print(f"\n✅ 총 {len(videos)}개 영상 수집 완료")
    
    # 결과 저장
    output_path = Path(__file__).parent / "recent_videos.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(videos, f, indent=2, ensure_ascii=False)
    
    print(f"  💾 영상 목록 저장: {output_path.name}")

