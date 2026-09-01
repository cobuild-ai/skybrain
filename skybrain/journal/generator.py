import os
from typing import List, Dict
from .parser import JournalEntry

def generate_dashboard_markdown(entries: List[JournalEntry], rel_base_dir: str = "2026") -> str:
    """
    Generate a clean, beautiful GitHub-native markdown dashboard from parsed journal entries.
    """
    sorted_entries = sorted(entries, key=lambda e: e.date, reverse=True)

    total_entries = len(sorted_entries)
    latest_date = sorted_entries[0].date if sorted_entries else "N/A"

    tag_counts: Dict[str, int] = {}
    for entry in sorted_entries:
        for t in entry.tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

    md = []
    md.append("# 📓 Engineering Daily Journal Dashboard")
    md.append("")
    md.append("> **자동 생성 도구:** `SkyBrain Journal Engine v1.0`  ")
    md.append(f"> **총 기록 일수:** {total_entries}일  ")
    md.append(f"> **최근 갱신일:** {latest_date}  ")
    md.append("> **보안 원칙:** 100% On-Device Zero Data Loss & Zero Leakage")
    md.append("")
    md.append("---")
    md.append("")

    if sorted_tags:
        md.append("## 🏷️ 주요 기술 태그 및 관심 영역 (Focus Tags)")
        md.append("")
        tag_badges = [f"`#{t}` ({c})" for t, c in sorted_tags[:12]]
        md.append(" • ".join(tag_badges))
        md.append("")
        md.append("---")
        md.append("")

    md.append("## 📅 일자별 엔지니어링 일지 총람 (Engineering Timeline)")
    md.append("")
    md.append("| 날짜 (Date) | 핵심 업무 및 기술 의사결정 요약 | 주요 태그 |")
    md.append("| :---: | :--- | :--- |")

    for entry in sorted_entries:
        rel_link = f"{rel_base_dir}/{entry.filename}"
        date_link = f"[{entry.date}]({rel_link})"

        if entry.key_tasks:
            tasks_summary = "<br>• ".join(entry.key_tasks[:2])
            summary_cell = f"**{entry.title}**<br>• {tasks_summary}"
        else:
            summary_cell = f"**{entry.title}**"

        if entry.tags:
            tags_cell = " ".join([f"`#{t}`" for t in entry.tags[:3]])
        else:
            tags_cell = "-"

        md.append(f"| {date_link} | {summary_cell} | {tags_cell} |")

    md.append("")
    md.append("---")
    md.append("")
    md.append("## 💡 빠른 실행 안내")
    md.append("```bash")
    md.append("# 대시보드 갱신 및 무손실 백업 실행")
    md.append("make journal-index")
    md.append("```")
    md.append("")

    return "\n".join(md)
