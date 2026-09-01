import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class JournalEntry:
    filepath: str
    filename: str
    date: str
    title: str
    tags: List[str] = field(default_factory=list)
    key_tasks: List[str] = field(default_factory=list)
    ai_insights: List[str] = field(default_factory=list)
    related_links: List[str] = field(default_factory=list)
    raw_content: str = ""

def parse_markdown_file(filepath: str) -> Optional[JournalEntry]:
    """Parse a single markdown journal file and extract structured metadata."""
    if not os.path.exists(filepath):
        return None

    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Parse Frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    date_str = ""
    tags: List[str] = []

    if frontmatter_match:
        fm_text = frontmatter_match.group(1)
        # Parse date
        date_m = re.search(r"^date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", fm_text, re.MULTILINE)
        if date_m:
            date_str = date_m.group(1)
        # Parse tags
        tags_m = re.search(r"^tags:\s*\[(.*?)\]", fm_text, re.MULTILINE)
        if tags_m:
            raw_tags = tags_m.group(1).split(",")
            tags = [t.strip().strip("'\"") for t in raw_tags if t.strip()]
        else:
            # Multi-line tags
            tags_block_m = re.search(r"^tags:\s*\n((?:\s*-\s*.*\n?)+)", fm_text, re.MULTILINE)
            if tags_block_m:
                lines = tags_block_m.group(1).strip().split("\n")
                tags = [re.sub(r"^\s*-\s*", "", l).strip() for l in lines if l.strip()]

    # Fallback date from filename if not in frontmatter
    if not date_str:
        fn_date_m = re.search(r"([0-9]{4}-[0-9]{2}-[0-9]{2})", filename)
        if fn_date_m:
            date_str = fn_date_m.group(1)
        else:
            date_str = "Unknown Date"

    # 2. Parse Title (# YYYY-MM-DD: [Title] or # [Title])
    title = ""
    title_m = re.search(r"^#\s*(?:[0-9]{4}-[0-9]{2}-[0-9]{2}:\s*)?(.*)$", content, re.MULTILINE)
    if title_m:
        title = title_m.group(1).strip()
    if not title:
        title = os.path.splitext(filename)[0]

    # 3. Parse Key Tasks (## 🚀 주요 업무 내용)
    key_tasks: List[str] = []
    tasks_section_m = re.search(r"##\s*🚀\s*주요\s*업무\s*내용\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if tasks_section_m:
        raw_tasks_block = tasks_section_m.group(1)
        bullets = re.findall(r"^(?:[0-9]+\.|\-)\s*\*\*(.*?)\*\*", raw_tasks_block, re.MULTILINE)
        if bullets:
            key_tasks = [b.strip() for b in bullets if b.strip()]
        else:
            raw_lines = [l.strip() for l in raw_tasks_block.split("\n") if l.strip().startswith(("-", "*", "1.", "2.", "3.", "4.", "5."))]
            key_tasks = [re.sub(r"^(?:[0-9]+\.|\-|\*)\s*", "", l).strip() for l in raw_lines[:4]]

    # 4. Parse AI Insights (## 📝 AI Insight)
    ai_insights: List[str] = []
    insights_m = re.search(r"##\s*📝\s*AI\s*Insight.*?\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if insights_m:
        raw_insights = insights_m.group(1)
        bullets = re.findall(r"^\s*-\s*\*\*(.*?)\*\*:\s*(.*)$", raw_insights, re.MULTILINE)
        if bullets:
            ai_insights = [f"{b[0]}: {b[1]}" for b in bullets]
        else:
            raw_lines = [l.strip() for l in raw_insights.split("\n") if l.strip().startswith("-")]
            ai_insights = [re.sub(r"^\s*-\s*", "", l).strip() for l in raw_lines[:2]]

    return JournalEntry(
        filepath=filepath,
        filename=filename,
        date=date_str,
        title=title,
        tags=tags,
        key_tasks=key_tasks,
        ai_insights=ai_insights,
        raw_content=content,
    )
