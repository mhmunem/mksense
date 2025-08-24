#!/usr/bin/env python
# coding: utf-8

get_ipython().run_line_magic('load_ext', 'autoreload')
get_ipython().run_line_magic('autoreload', '2')


import re
import json
from pathlib import Path
from tqdm.auto import tqdm
from loguru import logger
from typing import List, Dict, Optional

from mksense.config import EXTERNAL_DATA_DIR, RAW_DATA_DIR


def extract_markdown_title(content: str) -> Optional[str]:
    """
    Extract title from .md file.
    Looks for the first top-level heading: '# Title' or 'Title\n==='
    """
    lines = content.strip().splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line.startswith("#"):
            continue  # Skip multiline # blocks for now
    # Check Setext-style: Title\n===
    if len(lines) >= 2:
        title = lines[0].strip()
        underline = lines[1].strip()
        if underline and all(c in "=~" for c in underline) and len(underline) >= len(title):
            return title
    return None


def extract_rst_title(content: str) -> Optional[str]:
    """
    Extract title from .rst file.
    Looks for overlined+underlined or underlined-only headings with = or ~.
    """
    lines = content.strip().splitlines()
    if len(lines) < 2:
        return None

    # Pattern 1: Overlined and underlined: \n===\nTitle\n===\n
    for i in range(len(lines) - 2):
        prev = lines[i].strip()
        title_line = lines[i + 1].strip()
        underline = lines[i + 2].strip()

        if (
            underline
            and title_line
            and not prev  # empty or whitespace
            and all(c == "=" for c in underline)  # or "~" for sections
            and len(underline) >= len(title_line)
        ):
            return title_line

    # Pattern 2: Underlined only: Title\n===
    for i in range(len(lines) - 1):
        title_line = lines[i].strip()
        underline = lines[i + 1].strip()
        if (
            title_line
            and underline
            and all(c in "=~-" for c in underline)
            and len(underline) >= len(title_line)
            and not re.match(r"^[\d\.\s]+$", title_line)  # avoid version numbers
        ):
            return title_line

    return None


def parse_docs_to_json_with_titles(
    root_dir: Path,
    output_json: Path,
    repo_name: str,
    allowed_extensions: List[str] = ['.rst', '.md', '.py']
):
    """
    Recursively reads .rst, .md, and .py files, extracts title (if applicable), and saves to JSON.
    """
    root_dir = Path(root_dir)
    output_json = Path(output_json)

    if not root_dir.exists():
        raise FileNotFoundError(f"Directory not found: {root_dir}")

    documents: List[Dict] = []
    ext_count = {ext: 0 for ext in allowed_extensions}

    logger.info(f"Scanning {root_dir} for {allowed_extensions} files and extracting titles...")

    for ext in allowed_extensions:
        ext_pattern = f"**/*{ext}"
        files = list(root_dir.rglob(ext_pattern))

        for file_path in tqdm(files):
            if file_path.is_file():
                try:
                    relative_path = file_path.relative_to(root_dir)
                    content = file_path.read_text(encoding="utf-8", errors="ignore")

                    # Initialize metadata
                    title = None
                    file_ext = ext.lstrip(".")

                    # Extract title only for .md and .rst
                    if file_ext == "md":
                        title = extract_markdown_title(content)
                    elif file_ext == "rst":
                        title = extract_rst_title(content)

                    # Use first non-empty line as fallback if no title found
                    if not title:
                        first_lines = [line.strip() for line in content.splitlines() if line.strip()]
                        if first_lines:
                            title = first_lines[0][:100]  # Fallback: first meaningful line

                    documents.append({
                        "file_path": str(relative_path).replace("\\", "/"),
                        "extension": file_ext,
                        "title": title,
                        "content": content,
                        "repo": repo_name
                    })

                    ext_count[ext] += 1
                    # logger.debug(f"📄 Parsed: {relative_path} | Title: {title or '[No Title]'}")

                except Exception as e:
                    logger.warning(f"⚠️ Failed to read {file_path}: {e}")

    # Save to JSON
    output_json.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        logger.success(f"✅ Saved {len(documents)} documents to {output_json}")

        # Summary
        for ext, count in ext_count.items():
            logger.info(f"📊 {ext}: {count} files")
        logger.info(f"🎉 Total files processed: {len(documents)}")

    except Exception as e:
        logger.error(f"💥 Failed to write JSON file: {e}")
        raise


repo = "scikit-learn"
downloaded_dir = EXTERNAL_DATA_DIR / repo
output_file = RAW_DATA_DIR / f"{repo}_docs.json"

parse_docs_to_json_with_titles(
    root_dir=downloaded_dir,
    output_json=output_file,
    repo_name=repo,
    allowed_extensions=['.rst', '.md', '.py']
)

