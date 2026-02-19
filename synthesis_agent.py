"""
Synthesis Agent - 자막 기반 팟캐스트 스크립트 생성

이전 방식: Playwright로 NotebookLM UI 조작 (한국어 셀렉터 문제로 반복 실패)
새로운 방식: 수집된 자막 텍스트를 프롬프트에 직접 넣어 팟캐스트 스크립트 생성

왜 변경했는가:
- NotebookLM UI 자동화는 셀렉터 변경에 극도로 취약
- 자막을 직접 처리하면 브라우저 의존성이 완전히 제거됨
- 프롬프트 엔지니어링으로 동일한 품질의 스크립트 생성 가능
"""

import json
import os
from datetime import datetime
from pathlib import Path


# ──────────────────────────────────────────────
# 팟캐스트 스크립트 생성 프롬프트
# ──────────────────────────────────────────────
PODCAST_PROMPT_TEMPLATE = """당신은 한국의 인기 경제/투자 팟캐스트 진행자입니다.
아래 영상들의 자막을 분석하여, 청취자가 쉽게 이해할 수 있는 팟캐스트 대본을 작성해주세요.

## 작성 규칙
1. **형식**: 두 명의 진행자(A, B)가 대화하는 형식
2. **길이**: 약 3000~5000자
3. **톤**: 전문적이면서도 친근한 대화체
4. **구조**:
   - 🎙️ 오프닝 인사 (오늘의 주제 소개)
   - 📊 핵심 뉴스/인사이트 정리 (영상별)
   - 💡 심층 분석 및 의견
   - 📌 마무리 요약 및 액션 아이템
5. **한국어**로 작성

## 오늘의 영상 자료

{video_sections}

## 지시사항
위 영상 자료를 바탕으로 팟캐스트 대본을 작성해주세요.
각 영상의 핵심 포인트를 자연스럽게 대화에 녹여내고,
청취자에게 실질적인 인사이트를 제공하는 것이 목표입니다.
"""


def build_video_sections(videos: list[dict]) -> str:
    """
    영상 목록과 자막을 프롬프트 삽입용 섹션으로 변환.
    """
    sections = []
    for i, video in enumerate(videos, 1):
        transcript_path = Path(__file__).parent / f"transcript_{video['video_id']}.txt"
        transcript = ""
        if transcript_path.exists():
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript = f.read()
            # 너무 긴 자막은 앞부분만 사용 (토큰 제한 고려)
            if len(transcript) > 8000:
                transcript = transcript[:8000] + "\n... (이하 생략)"
        
        section = f"""### 영상 {i}: {video['title']}
- **채널**: {video.get('channel', 'N/A')}
- **URL**: {video['url']}

**자막 내용:**
{transcript if transcript else '(자막 없음)'}
"""
        sections.append(section)
    
    return "\n---\n".join(sections)


def generate_script_with_prompt(videos: list[dict]) -> str:
    """
    자막 데이터를 기반으로 팟캐스트 스크립트 프롬프트를 구성한다.
    
    NOTE: 이 함수는 프롬프트만 생성합니다.
    실제 LLM 호출은 main.py에서 notebooklm MCP 또는 다른 방식으로 수행합니다.
    현재는 프롬프트 자체를 반환하되, 간단한 자체 요약도 함께 생성합니다.
    """
    video_sections = build_video_sections(videos)
    prompt = PODCAST_PROMPT_TEMPLATE.format(video_sections=video_sections)
    return prompt


def generate_local_script(videos: list[dict]) -> str:
    """
    LLM API 없이 로컬에서 기본 팟캐스트 스크립트를 생성한다.
    자막 내용을 구조화하여 대본 형태로 변환.
    """
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    script_parts = []
    script_parts.append(f"# 🎙️ 데일리 투자 브리핑 — {today}\n")
    script_parts.append("## 오프닝\n")
    script_parts.append(f"**A**: 안녕하세요! {today} 데일리 투자 브리핑입니다.")
    script_parts.append(f"**B**: 오늘은 총 {len(videos)}개의 영상에서 핵심 인사이트를 정리해봤습니다.\n")
    
    for i, video in enumerate(videos, 1):
        script_parts.append(f"---\n## 📊 영상 {i}: {video['title']}")
        script_parts.append(f"*채널: {video.get('channel', 'N/A')} | [영상 링크]({video['url']})*\n")
        
        transcript_path = Path(__file__).parent / f"transcript_{video['video_id']}.txt"
        if transcript_path.exists():
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript = f.read()
            
            # 핵심 문장 추출 (첫 500자 + 마지막 300자)
            if len(transcript) > 1000:
                summary = transcript[:500] + "\n\n... (중략) ...\n\n" + transcript[-300:]
            else:
                summary = transcript
            
            script_parts.append(f"**A**: 이 영상의 핵심 내용을 정리해보면...")
            script_parts.append(f"\n> {summary}\n")
            script_parts.append(f"**B**: 흥미로운 포인트네요. 다음 영상으로 넘어가볼까요?\n")
        else:
            script_parts.append("**A**: 안타깝게도 이 영상은 자막이 제공되지 않아 내용을 확인할 수 없었습니다.\n")
    
    script_parts.append("---\n## 📌 마무리\n")
    script_parts.append("**A**: 오늘 브리핑 내용 정리해볼까요?")
    script_parts.append(f"**B**: 네, 오늘은 총 {len(videos)}개 영상의 핵심을 다뤘습니다.")
    script_parts.append("**A**: 내일도 새로운 인사이트로 찾아뵙겠습니다. 감사합니다! 🎙️\n")
    
    # 프롬프트도 함께 저장 (나중에 LLM으로 업그레이드할 때 사용)
    script_parts.append("\n---\n## 🤖 LLM 프롬프트 (향후 AI 생성용)\n")
    script_parts.append("아래 프롬프트를 LLM에 전달하면 더 자연스러운 대본을 생성할 수 있습니다:\n")
    script_parts.append("```")
    script_parts.append(generate_script_with_prompt(videos))
    script_parts.append("```")
    
    return "\n".join(script_parts)


class SynthesisAgent:
    """팟캐스트 스크립트를 생성하는 에이전트."""
    
    def __init__(self):
        self.output_dir = Path(__file__).parent
    
    def generate_podcast(self, videos: list[dict]) -> str | None:
        """
        수집된 영상 데이터로 팟캐스트 스크립트를 생성한다.
        
        Args:
            videos: research_agent에서 수집한 영상 목록
            
        Returns:
            생성된 스크립트 파일 경로, 실패시 None
        """
        if not videos:
            print("  영상이 없어 스크립트를 생성할 수 없습니다.")
            return None
        
        print(f"📝 {len(videos)}개 영상으로 팟캐스트 스크립트 생성 중...")
        
        # 로컬 스크립트 생성 (LLM API 없이)
        script = generate_local_script(videos)
        
        # 파일 저장
        today = datetime.now().strftime("%Y%m%d")
        output_path = self.output_dir / f"podcast_script_{today}.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script)
        
        print(f"  ✅ 스크립트 저장: {output_path.name}")
        print(f"  📄 분량: {len(script)}자")
        
        return str(output_path)


if __name__ == "__main__":
    # 테스트: recent_videos.json에서 읽어서 스크립트 생성
    videos_path = Path(__file__).parent / "recent_videos.json"
    if not videos_path.exists():
        print("❌ recent_videos.json을 찾을 수 없습니다. research_agent.py를 먼저 실행하세요.")
        exit(1)
    
    with open(videos_path, "r", encoding="utf-8") as f:
        videos = json.load(f)
    
    agent = SynthesisAgent()
    result = agent.generate_podcast(videos)
    if result:
        print(f"\n🎙️ 팟캐스트 스크립트 생성 완료: {result}")
