import os
import unittest
import tempfile
from skybrain.journal.parser import parse_markdown_file
from skybrain.journal.backup import backup_file, restore_backup
from skybrain.journal.generator import generate_dashboard_markdown

SAMPLE_MARKDOWN = """---
date: 2026-08-30
tags: [governance, litert, gemma]
---

# 2026-08-30: [문서 표준화 및 3-Tier 이관]

## 🚀 주요 업무 내용
1. **마스터 README 영문 표준화**: 시퀀스 다이어그램 및 톤앤매너 샘플 정제.
2. **실기기 500회 Monkey 스트레스 테스트**: 크래시 0건 검증.

## 📝 AI Insight (#from-ai)
- **오픈소스 대문 일관성**: 영문 대문 유지의 중요성.

## 🔗 관련 문서 및 링크
- [[GEMINI.md]]
"""

class TestSkyBrainJournal(unittest.TestCase):
    def test_parser(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(SAMPLE_MARKDOWN)
            f_path = f.name

        try:
            entry = parse_markdown_file(f_path)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.date, "2026-08-30")
            self.assertEqual(entry.title, "[문서 표준화 및 3-Tier 이관]")
            self.assertIn("governance", entry.tags)
            self.assertTrue(len(entry.key_tasks) >= 2)
            self.assertIn("마스터 README 영문 표준화", entry.key_tasks[0])
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_backup_and_restore(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(SAMPLE_MARKDOWN)
            f_path = f.name

        with tempfile.TemporaryDirectory() as b_dir:
            b_path = backup_file(f_path, backup_root=b_dir)
            self.assertIsNotNone(b_path)
            self.assertTrue(os.path.exists(b_path))
            self.assertTrue(b_path.endswith(".gz"))

            restore_target = os.path.join(b_dir, "restored.md")
            success = restore_backup(b_path, restore_target)
            self.assertTrue(success)
            with open(restore_target, "r", encoding="utf-8") as rf:
                restored_content = rf.read()
            self.assertEqual(restored_content, SAMPLE_MARKDOWN)

        if os.path.exists(f_path):
            os.remove(f_path)

    def test_dashboard_generation(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(SAMPLE_MARKDOWN)
            f_path = f.name

        try:
            entry = parse_markdown_file(f_path)
            dashboard = generate_dashboard_markdown([entry])
            self.assertIn("# 📓 Engineering Daily Journal Dashboard", dashboard)
            self.assertIn("2026-08-30", dashboard)
            self.assertIn("`#governance`", dashboard)
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

if __name__ == "__main__":
    unittest.main()
