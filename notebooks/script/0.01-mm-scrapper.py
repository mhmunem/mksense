#!/usr/bin/env python
# coding: utf-8

get_ipython().run_line_magic('load_ext', 'autoreload')
get_ipython().run_line_magic('autoreload', '2')


import os
import requests
from pathlib import Path
from loguru import logger
from urllib.parse import urlparse

from mksense.config import EXTERNAL_DATA_DIR
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup GitHub API authentication
github_api_key = os.environ.get("GITHUB_API_TOKEN")
if not github_api_key:
    logger.warning("GITHUB_API_TOKEN not found in environment. Proceeding without authentication (rate limits apply).")
    headers = {}
else:
    headers = {"Authorization": f"token {github_api_key}"}


def get_user_and_repo(github_link):
    """
    Extracts the owner and repo name from a GitHub link using urlparse.
    """
    if not github_link:
        raise ValueError("GitHub link is empty.")

    parsed = urlparse(github_link.strip())

    if parsed.netloc != "github.com":
        raise ValueError("Not a GitHub URL.")

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    if len(path_parts) < 2:
        raise ValueError("Invalid GitHub repository URL.")

    return path_parts[0], path_parts[1]



# Example usage
github_link = "https://github.com/scikit-learn/scikit-learn"
user, repo = get_user_and_repo(github_link)
logger.info(f"Extracted repository: user='{user}', repo='{repo}'")


def get_doc_folder_name(user: str, repo: str) -> str:
    """
    Checks which of the common documentation folders exists in the GitHub repo.

    Args:
        user (str): GitHub username or organization.
        repo (str): Repository name.

    Returns:
        str: Name of the first existing doc folder, or None if none exist.
    """
    common_doc_folders = ["docs", "doc", "documentation"]

    for folder in common_doc_folders:
        url = f"https://api.github.com/repos/{user}/{repo}/contents/{folder}"  # Fixed extra space
        logger.debug(f"Checking folder: {url}")
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            logger.success(f"Documentation folder found: '{folder}'")
            return folder
        elif response.status_code == 404:
            logger.debug(f"Folder '{folder}' not found.")
            continue
        else:
            logger.error(f"Error accessing {url}: {response.status_code} - {response.json().get('message', '')}")
            response.raise_for_status()

    logger.warning("No common documentation folder found.")
    return None


folder_name = get_doc_folder_name(user, repo)


folder_name


def get_docs_folder(user: str, repo: str, folder_path: str, save_path: Path):
    """
    Downloads the specified documentation folder from a GitHub repository recursively.

    Args:
        user (str): GitHub username or organization.
        repo (str): Repository name.
        folder_path (str): GitHub path of the folder (e.g., 'docs').
        save_path (Path): Local path to save the downloaded files.

    Raises:
        Exception: If downloading fails.
    """
    base_url = f"https://api.github.com/repos/{user}/{repo}/contents/"
    url = f"{base_url}{folder_path}"

    # Ensure parent directories exist
    save_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading content from '{folder_path}' to '{save_path}'")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch folder: {e}")
        raise Exception(f"Failed to fetch {url}: {e}")

    items = response.json()

    for item in items:
        item_path = Path(save_path) / item["name"]

        if item["type"] == "file":
            logger.info(f"📥 Downloading file: {item['name']} → {item_path}")
            try:
                file_response = requests.get(item["download_url"], headers=headers)
                file_response.raise_for_status()
                with open(item_path, "wb") as f:
                    f.write(file_response.content)
                logger.success(f"✅ Saved: {item_path}")
            except Exception as e:
                logger.error(f"❌ Failed to download {item['name']}: {e}")

        elif item["type"] == "dir":
            logger.info(f"📁 Entering directory: {item['path']}")
            get_docs_folder(user, repo, item["path"], item_path)



# Define save path
save_path = EXTERNAL_DATA_DIR / repo

if folder_name:
    try:
        get_docs_folder(user, repo, folder_name, save_path)
        logger.success(f"All documentation downloaded to: {save_path}")
    except Exception as e:
        logger.error(f"Failed to download documentation: {e}")
else:
    logger.warning(f"No documentation folder to download for {user}/{repo}.")




