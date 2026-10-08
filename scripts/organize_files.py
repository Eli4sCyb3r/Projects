#!/usr/bin/env python3
"""
organize_files.py — Safe, dry-run-first file organizer.

Scans the directories you specify, works out a clean destination tree for each
file (by extension, a peek at text-file contents, and modification date), and
either PREVIEWS the plan (default) or MOVES the files (only with --execute).

Nothing is ever deleted. Every real move is recorded in an undo manifest so the
whole operation can be reversed with --undo.

Quick start:
    # 1. Preview only (safe, writes a Markdown report, moves nothing):
    python3 organize_files.py --source ~/Downloads ~/Desktop --dest ~/Organized

    # 2. Read the report it prints the path to, tweak categories if desired.

    # 3. Actually move files:
    python3 organize_files.py --source ~/Downloads ~/Desktop --dest ~/Organized --execute

    # 4. Changed your mind? Reverse it:
    python3 organize_files.py --undo ~/Organized/.organize_undo_20260101-120000.json

Tested on Python 3.8+. Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURATION — tweak these to change how files are sorted.
# ---------------------------------------------------------------------------

# Map lowercase extensions -> top-level category folder.
EXTENSION_CATEGORIES = {
    # Documents
    ".pdf": "Documents",
    ".doc": "Documents", ".docx": "Documents", ".odt": "Documents",
    ".txt": "Documents", ".rtf": "Documents", ".md": "Documents",
    ".ppt": "Documents", ".pptx": "Documents",
    ".xls": "Documents/Spreadsheets", ".xlsx": "Documents/Spreadsheets",
    ".csv": "Documents/Spreadsheets", ".ods": "Documents/Spreadsheets",
    # Images
    ".jpg": "Media/Images", ".jpeg": "Media/Images", ".png": "Media/Images",
    ".gif": "Media/Images", ".bmp": "Media/Images", ".svg": "Media/Images",
    ".tiff": "Media/Images", ".webp": "Media/Images", ".heic": "Media/Images",
    # Video / Audio
    ".mp4": "Media/Video", ".mov": "Media/Video", ".avi": "Media/Video",
    ".mkv": "Media/Video", ".webm": "Media/Video",
    ".mp3": "Media/Audio", ".wav": "Media/Audio", ".flac": "Media/Audio",
    ".m4a": "Media/Audio", ".ogg": "Media/Audio",
    # Archives
    ".zip": "Archives", ".tar": "Archives", ".gz": "Archives",
    ".bz2": "Archives", ".7z": "Archives", ".rar": "Archives", ".xz": "Archives",
    # Code / dev
    ".py": "Code", ".js": "Code", ".ts": "Code", ".java": "Code",
    ".c": "Code", ".cpp": "Code", ".h": "Code", ".go": "Code",
    ".rs": "Code", ".rb": "Code", ".sh": "Code", ".pl": "Code",
    ".html": "Code", ".css": "Code", ".json": "Code", ".yaml": "Code",
    ".yml": "Code", ".xml": "Code", ".sql": "Code",
    # Installers / binaries
    ".exe": "Installers", ".msi": "Installers", ".dmg": "Installers",
    ".deb": "Installers", ".rpm": "Installers", ".appimage": "Installers",
}

# Extensions we are willing to peek inside for content-based refinement.
TEXT_PEEK_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log", ".html",
    ".py", ".js", ".ts", ".sql", ".ini", ".cfg", ".xml",
}

# Keyword buckets for the content peek. If a file's text matches a bucket,
# it gets routed into that subfolder instead of the generic category.
# Order matters: the first bucket with enough hits wins.
CONTENT_BUCKETS = {
    "Documents/Financial": [
        "invoice", "receipt", "payment", "tax", "salary", "budget",
        "bank", "statement", "paypal", "iban", "balance due",
    ],
    "Documents/Work": [
        "meeting", "agenda", "project plan", "deadline", "deliverable",
        "report", "proposal", "contract", "client",
    ],
    "Documents/Personal": [
        "resume", "cv", "passport", "medical", "prescription",
        "insurance", "appointment",
    ],
}
# How many keyword hits are needed before a content bucket overrides the
# extension-based category.
CONTENT_MATCH_THRESHOLD = 2

# Date-bucket these categories into a YYYY/ subfolder by modification time.
DATE_BUCKET_CATEGORIES = {"Media/Images", "Media/Video", "Media/Audio", "Archives"}

# Anything whose extension is unknown lands here.
FALLBACK_CATEGORY = "Misc"

# Directories we must never descend into (case-insensitive substring match on
# the absolute path). Protects the OS and avoids touching other tooling.
EXCLUDED_PATH_FRAGMENTS = {
    # Windows
    "windows", "program files", "program files (x86)", "programdata",
    "appdata", "$recycle.bin", "system volume information",
    # macOS / Linux system
    "/system/", "/library/", "/private/", "/bin/", "/sbin/", "/usr/",
    "/etc/", "/var/", "/proc/", "/dev/", "/boot/", "/lib/",
    # Dev/junk we don't want to shuffle
    "node_modules", ".git", "__pycache__", ".venv", "venv",
}

# Skip files bigger than this many MB when peeking at content (we still move
# them; we just don't read them). Set generously.
MAX_PEEK_MB = 2

# Read at most this many bytes when peeking at a text file.
PEEK_BYTES = 8192


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_excluded(path: Path) -> bool:
    """True if the path lives under a protected/system/junk directory."""
    lowered = str(path).lower().replace("\\", "/")
    return any(frag in lowered for frag in EXCLUDED_PATH_FRAGMENTS)


def short_hash(path: Path, block: int = 65536) -> str:
    """First 8 hex chars of the file's SHA-256 (used for dedupe + collisions)."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(block), b""):
                h.update(chunk)
    except OSError:
        return "nohash"
    return h.hexdigest()[:8]


def peek_category(path: Path, default: str) -> str:
    """Refine a category by scanning the start of a text file for keywords."""
    if path.suffix.lower() not in TEXT_PEEK_EXTENSIONS:
        return default
    try:
        if path.stat().st_size > MAX_PEEK_MB * 1024 * 1024:
            return default
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read(PEEK_BYTES).lower()
    except OSError:
        return default

    for bucket, keywords in CONTENT_BUCKETS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits >= CONTENT_MATCH_THRESHOLD:
            return bucket
    return default


def categorize(path: Path) -> str:
    """Decide the destination category folder (relative to --dest) for a file."""
    ext = path.suffix.lower()
    category = EXTENSION_CATEGORIES.get(ext, FALLBACK_CATEGORY)
    category = peek_category(path, category)

    if category in DATE_BUCKET_CATEGORIES:
        try:
            year = _dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y")
        except OSError:
            year = "unknown-date"
        category = f"{category}/{year}"
    return category


def resolve_collision(dest: Path, src: Path, planned: set) -> Path:
    """Return a non-colliding destination path, disambiguating with a hash."""
    if not dest.exists() and dest not in planned:
        return dest
    tag = short_hash(src)
    candidate = dest.with_name(f"{dest.stem}__{tag}{dest.suffix}")
    # Extremely unlikely, but guard against a double collision.
    counter = 1
    while candidate.exists() or candidate in planned:
        candidate = dest.with_name(f"{dest.stem}__{tag}_{counter}{dest.suffix}")
        counter += 1
    return candidate


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def build_plan(sources, dest_root: Path):
    """Walk sources and return (plan, duplicates).

    plan: list of (src_path, dest_path, category)
    duplicates: list of (src_path, matching_earlier_src) with identical hashes
    """
    plan = []
    planned_dests = set()
    seen_hashes = {}      # hash -> first source path
    duplicates = []

    for source in sources:
        source = source.expanduser().resolve()
        if not source.exists():
            print(f"[!] Source does not exist, skipping: {source}", file=sys.stderr)
            continue
        for root, dirs, files in os.walk(source):
            root_path = Path(root)
            # Prune excluded / hidden directories in-place so we never descend.
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and not is_excluded(root_path / d)
            ]
            for name in files:
                src = root_path / name
                if name.startswith(".") or src.is_symlink() or is_excluded(src):
                    continue
                if not src.is_file():
                    continue

                # Note identical-content duplicates (reported, still moved safely).
                digest = short_hash(src)
                if digest != "nohash":
                    if digest in seen_hashes:
                        duplicates.append((src, seen_hashes[digest]))
                    else:
                        seen_hashes[digest] = src

                category = categorize(src)
                dest = resolve_collision(
                    dest_root / category / name, src, planned_dests
                )
                planned_dests.add(dest)
                plan.append((src, dest, category))
    return plan, duplicates


def write_report(plan, duplicates, dest_root: Path, executed: bool) -> Path:
    """Write a Markdown preview/summary report and return its path."""
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = dest_root / f"organize_report_{stamp}.md"
    dest_root.mkdir(parents=True, exist_ok=True)

    by_category = {}
    for _src, _dest, cat in plan:
        by_category.setdefault(cat, 0)
        by_category[cat] += 1

    lines = [
        f"# File organization {'result' if executed else 'preview'}",
        "",
        f"- Generated: {_dt.datetime.now().isoformat(timespec='seconds')}",
        f"- Mode: {'EXECUTED (files moved)' if executed else 'DRY RUN (nothing moved)'}",
        f"- Destination root: `{dest_root}`",
        f"- Files planned: **{len(plan)}**",
        f"- Identical-content duplicates detected: **{len(duplicates)}**",
        "",
        "## Proposed structure (file count per folder)",
        "",
    ]
    for cat in sorted(by_category):
        lines.append(f"- `{cat}/` — {by_category[cat]} file(s)")

    lines += ["", "## Full mapping", "", "| Source | → | Destination |", "|---|---|---|"]
    for src, dest, _cat in plan:
        lines.append(f"| `{src}` | → | `{dest}` |")

    if duplicates:
        lines += ["", "## Duplicate contents (same bytes)", ""]
        for dup, original in duplicates:
            lines.append(f"- `{dup}` is identical to `{original}`")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def execute_plan(plan, dest_root: Path) -> Path:
    """Perform the moves and write an undo manifest. Returns the manifest path."""
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_path = dest_root / f".organize_undo_{stamp}.json"
    moves = []

    for src, dest, _cat in plan:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            moves.append({"from": str(src), "to": str(dest)})
        except OSError as exc:
            print(f"[!] Failed to move {src} -> {dest}: {exc}", file=sys.stderr)

    manifest_path.write_text(
        json.dumps({"created": stamp, "moves": moves}, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def undo(manifest_file: Path) -> None:
    """Reverse a previous execution using its undo manifest."""
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    moves = data.get("moves", [])
    restored = 0
    # Reverse order so nested dirs unwind cleanly.
    for entry in reversed(moves):
        src = Path(entry["to"])        # where the file is now
        dst = Path(entry["from"])      # where it originally lived
        if not src.exists():
            print(f"[!] Missing, cannot restore: {src}", file=sys.stderr)
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                dst = resolve_collision(dst, src, set())
            shutil.move(str(src), str(dst))
            restored += 1
        except OSError as exc:
            print(f"[!] Failed to restore {src} -> {dst}: {exc}", file=sys.stderr)
    print(f"[#] Restored {restored}/{len(moves)} file(s).")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Safe, dry-run-first file organizer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--source", "-s", nargs="+",
                   help="One or more source directories to scan.")
    p.add_argument("--dest", "-d",
                   help="Destination root for the organized tree.")
    p.add_argument("--execute", action="store_true",
                   help="Actually move files. Omit for a safe dry run.")
    p.add_argument("--undo", metavar="MANIFEST",
                   help="Reverse a previous run using its undo JSON manifest.")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.undo:
        manifest = Path(args.undo).expanduser().resolve()
        if not manifest.is_file():
            sys.exit(f"[!] Undo manifest not found: {manifest}")
        undo(manifest)
        return

    if not args.source or not args.dest:
        sys.exit("[!] --source and --dest are required (unless using --undo).")

    sources = [Path(s) for s in args.source]
    dest_root = Path(args.dest).expanduser().resolve()

    # Guard: never let the destination sit inside a source (infinite recursion).
    for s in sources:
        s_res = s.expanduser().resolve()
        if dest_root == s_res or dest_root in s_res.parents or s_res in dest_root.parents:
            sys.exit(f"[!] Destination {dest_root} overlaps source {s_res}. "
                     "Choose a destination outside your source directories.")

    print(f"[*] Scanning {len(sources)} source(s)...")
    plan, duplicates = build_plan(sources, dest_root)
    print(f"[*] Planned {len(plan)} file(s); {len(duplicates)} duplicate(s) noted.")

    if not args.execute:
        report = write_report(plan, duplicates, dest_root, executed=False)
        print(f"[#] DRY RUN complete. No files were moved.")
        print(f"[#] Review the plan here:\n    {report}")
        print(f"[#] When satisfied, re-run with --execute to move the files.")
        return

    print("[*] EXECUTE mode: moving files...")
    manifest = execute_plan(plan, dest_root)
    report = write_report(plan, duplicates, dest_root, executed=True)
    print(f"[#] Done. Moved files recorded in:\n    {manifest}")
    print(f"[#] Summary report:\n    {report}")
    print(f"[#] To undo everything:\n    python3 {Path(__file__).name} --undo {manifest}")


if __name__ == "__main__":
    main()
