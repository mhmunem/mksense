#!/usr/bin/env python
# coding: utf-8

get_ipython().run_line_magic('load_ext', 'autoreload')
get_ipython().run_line_magic('autoreload', '2')


import json
import re
import sys
from pathlib import Path
from loguru import logger
from tqdm.auto import tqdm


# Setup logger
logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add("cleaning.log", level="DEBUG", rotation="10 MB")


from mksense.config import RAW_DATA_DIR, PROCESSED_DATA_DIR


def clean_rst_syntax(text: str) -> str:
    """Remove reStructuredText roles, directives, and links."""
    if not isinstance(text, str):
        return ""
    # Remove :role:`text`
    text = re.sub(r":(func|class|mod|ref|issue|user|arxiv|citet|cite|pep|doc|download|command|option|envvar|term|ref):`[^`]+`", "", text)
    # Remove _`inline references`
    text = re.sub(r"_`[^`]+`", "", text)
    # Convert ``code`` to 'code'
    text = re.sub(r"``([^`]+)``", r"'\1'", text)
    # Convert `text <url>`_ to text
    text = re.sub(r"`([^`]+) <[^>]+>`_", r"\1", text)
    # Remove labels like .. _label:
    text = re.sub(r"\.\. _[a-zA-Z0-9_]+:", "", text)
    # Remove directives
    text = re.sub(r"\.\. (note|warning|tip|seealso|rubric|code-block|highlight)::.*?(?=\n\S)", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def clean_code_and_prompts(text: str) -> str:
    """Remove >>>, ..., and code block markers."""
    text = re.sub(r"^\s*>>> ", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\.\.\. ", "", text, flags=re.MULTILINE)
    # Replace code blocks with placeholder
    text = re.sub(r"::\s*\n(.*?)(?=\n\S)", "[Code Block]", text, flags=re.DOTALL)
    return text


def clean_metadata_dicts(text: str) -> str:
    """Remove inline Python dict literals like 'tag': [...]"""
    text = re.sub(r"'[a-zA-Z_]+[^,}'\"]*?[:][^,}]*?[,}]", "", text)
    return text


def clean_general_noise(text: str) -> str:
    """Remove common noise: doctest, SKIP, etc."""
    noise_patterns = [
        r"# doctest: \+\w+",
        r":orphan:",
        r"\.\.\. currentmodule::.*",
        r"\.\.\. autosummary::",
        r"\.\.\. include::.*",
        r"__",
        r"\^[\w-]+`",
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def clean_text(text: str) -> str:
    """Apply all cleaning steps."""
    if not text or not isinstance(text, str):
        return ""
    text = clean_rst_syntax(text)
    text = clean_code_and_prompts(text)
    text = clean_metadata_dicts(text)
    text = clean_general_noise(text)
    return text.strip()


def extract_title_from_content(content: str) -> str:
    """Try to extract a meaningful title from content."""
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return "Untitled"

    # Look for Setext-style heading: Title\n====
    if len(lines) > 1:
        first, second = lines[0], lines[1]
        if len(second) >= len(first) and all(c in "=~-_" for c in second):
            return first

    # Fallback: first non-empty, non-code line
    for line in lines:
        if len(line) < 100 and not line.startswith((".. ", ">>>", "::", "import", "from")):
            return line
    return lines[0][:60] + "..." if len(lines[0]) > 60 else lines[0]


def build_context_from_path(file_path: str) -> str:
    """Build hierarchical context from file path."""
    path_obj = Path(file_path)
    parts = path_obj.parts[:-1]  # Exclude filename
    cleaned_parts = [
        p.replace(".rst", "").replace(".md", "").replace("_", " ").title()
        for p in parts
    ]
    return " → ".join(cleaned_parts)


def clean_json(
    input_json: Path,
    output_json: Path
):
    """
    Load, clean, and restructure scikit-learn docs into:
    {
      "repo": "scikit-learn",
      "documents": [ {...}, ... ]
    }
    One document per file (no chunking).
    """
    input_json = Path(input_json)
    output_json = Path(output_json)

    logger.info(f"Loading JSON from {input_json}")
    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON must be a list of document objects")

    cleaned_docs = []

    for doc in tqdm(data, desc="Cleaning documents"):
        file_path = doc.get("file_path", "unknown")
        raw_content = doc.get("content", "")
        extension = doc.get("extension", Path(file_path).suffix.lstrip("."))
        repo = doc.get("repo")

        # Clean content
        cleaned_content = clean_text(raw_content)
        if not cleaned_content:
            continue  # Skip empty docs

        # Extract or use title
        title = doc.get("title") or extract_title_from_content(cleaned_content)

        # Build context
        context = doc.get("context") or build_context_from_path(file_path)

        cleaned_docs.append({
            "content": cleaned_content,
            "file_path": file_path,
            "title": title,
            "context": context,
            "extension": extension,
            "repo":repo
        })

    # Save output
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cleaned_docs, f, indent=2, ensure_ascii=False)

    logger.success(f"✅ Cleaned {len(cleaned_docs)} documents saved to {output_json}")
    logger.info(f"📄 Output structure: {{'repo': 'scikit-learn', 'documents': [...] }}")


repo = "pytorch"
input_file = RAW_DATA_DIR / repo / f"{repo}_docs.json"   # Update path as needed
output_file = PROCESSED_DATA_DIR / repo / f"{repo}_docs_cleaned.json"
clean_json(input_file, output_file)




