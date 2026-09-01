import os
import sys
import glob
import argparse
from typing import List

from .parser import parse_markdown_file, JournalEntry
from .backup import backup_file, calculate_sha256, calculate_gzip_content_sha256
from .generator import generate_dashboard_markdown

def run_index(source_dir: str, output_file: str, backup_dir: str, enable_backup: bool = True):
    """Scan source_dir for markdown files, backup, parse, and generate dashboard."""
    if not os.path.exists(source_dir):
        print(f"❌ Error: Source directory does not exist: {source_dir}")
        sys.exit(1)

    md_files = sorted(glob.glob(os.path.join(source_dir, "*.md")))
    if not md_files:
        print(f"⚠️ Warning: No markdown files found in {source_dir}")
        sys.exit(0)

    print(f"🔍 SkyBrain Journal: Scanning {len(md_files)} journal files in '{source_dir}'...")

    newly_backed_up = 0
    unchanged_backed_up = 0
    entries: List[JournalEntry] = []

    for filepath in md_files:
        if enable_backup:
            filename = os.path.basename(filepath)
            existing_backups = sorted(glob.glob(os.path.join(backup_dir, f"*_{filename}.gz")))
            had_prior = len(existing_backups) > 0
            
            b_path = backup_file(filepath, backup_root=backup_dir)
            if b_path:
                if had_prior and b_path == existing_backups[-1]:
                    unchanged_backed_up += 1
                else:
                    newly_backed_up += 1

        entry = parse_markdown_file(filepath)
        if entry:
            entries.append(entry)

    rel_base_dir = os.path.basename(os.path.normpath(source_dir))
    dashboard_md = generate_dashboard_markdown(entries, rel_base_dir=rel_base_dir)

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(dashboard_md)

    print(f"✅ SkyBrain Journal Indexing Complete:")
    print(f"   • Parsed:   {len(entries)} journal entries")
    if enable_backup:
        if newly_backed_up > 0:
            print(f"   • Backups:  {newly_backed_up} new backups created, {unchanged_backed_up} unchanged (skipped)")
        else:
            print(f"   • Backups:  All {unchanged_backed_up} files are already up-to-date in '{backup_dir}' (0 wasted)")
    print(f"   • Output:   '{output_file}' updated cleanly!")

def main():
    parser = argparse.ArgumentParser(description="SkyBrain Journal: Markdown Indexer & Zero-Loss Archiver")
    parser.add_argument("command", nargs="?", default="index", help="Subcommand (default: index)")
    parser.add_argument("--source", "-s", default="Journal/2026", help="Path to journal markdown directory")
    parser.add_argument("--output", "-o", default="Journal/README.md", help="Path to output dashboard README.md")
    parser.add_argument("--backup-dir", "-b", default=".skyjournal/backups", help="Path to store compressed backups")
    parser.add_argument("--no-backup", action="store_true", help="Disable automatic .gz backups")

    args = parser.parse_args()

    enable_backup = not args.no_backup
    run_index(
        source_dir=args.source,
        output_file=args.output,
        backup_dir=args.backup_dir,
        enable_backup=enable_backup
    )

if __name__ == "__main__":
    main()
