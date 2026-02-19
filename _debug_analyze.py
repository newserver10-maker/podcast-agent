"""디버그 HTML 분석 — 오디오 개요 UI 구조 심층 분석"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

debug_file = Path('e:/Anti gravity/podcast_agent/debug_audio_section.html')
if not debug_file.exists():
    print("debug_audio_section.html not found, trying debug_audio_tab.html")
    debug_file = Path('e:/Anti gravity/podcast_agent/debug_audio_tab.html')

content = debug_file.read_text(encoding='utf-8', errors='ignore')

# 1. audio-overview 관련 HTML 태그 찾기
audio_tags = re.findall(r'<audio-overview[^>]*>(.{0,500})</audio-overview>', content, re.DOTALL)
print(f'=== AUDIO-OVERVIEW TAGS ({len(audio_tags)}) ===')
for t in audio_tags[:5]:
    clean = re.sub(r'<[^>]+>', ' ', t).strip()
    print(f'  {clean[:200]}')

# audio-overview 태그 속성
audio_attrs = re.findall(r'<audio-overview([^>]*)>', content)
print(f'\n=== AUDIO-OVERVIEW ATTRS ({len(audio_attrs)}) ===')
for a in audio_attrs[:5]:
    print(f'  {a[:200]}')

# 2. 노트북 가이드 패널
guides = re.findall(r'<notebook-guide[^>]*>(.{0,1000})</notebook-guide>', content, re.DOTALL)
print(f'\n=== NOTEBOOK-GUIDE ({len(guides)}) ===')
for g in guides[:3]:
    clean = re.sub(r'<[^>]+>', ' | ', g).strip()
    print(f'  {clean[:300]}')

# 3. mat-tab-label 찾기
tab_labels = re.findall(r'mat-tab-label[^>]*>(.{0,200})', content, re.DOTALL)
print(f'\n=== MAT-TAB-LABELS ({len(tab_labels)}) ===')
for tl in tab_labels[:10]:
    clean = re.sub(r'<[^>]+>', ' ', tl).strip()
    print(f'  {clean[:100]}')

# 4. 우측 패널 구조 (소스 + 가이드 패널)
panels = re.findall(r'class="[^"]*(?:right-panel|side-panel|source-panel|guide-panel|studio-panel)[^"]*"', content)
print(f'\n=== PANEL CLASSES ({len(panels)}) ===')
for p in panels[:10]:
    print(f'  {p[:120]}')

# 5. heading (h1, h2, h3)  
headings = re.findall(r'<h[1-3][^>]*>(.*?)</h[1-3]>', content, re.DOTALL)
print(f'\n=== HEADINGS ({len(headings)}) ===')
for h in headings[:10]:
    clean = re.sub(r'<[^>]+>', '', h).strip()
    if clean:
        print(f'  {clean[:80]}')

# 6. section 역할 요소
sections = re.findall(r'class="[^"]*(?:section|overview|guide|audio)[^"]*"[^>]*>(.{0,200})', content, re.DOTALL)
print(f'\n=== SECTION/OVERVIEW ELEMENTS ({len(sections)}) ===')
for s in sections[:10]:
    clean = re.sub(r'<[^>]+>', ' ', s).strip()
    if clean:
        print(f'  {clean[:100]}')
