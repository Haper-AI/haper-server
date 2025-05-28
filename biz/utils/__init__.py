import os
import re
import traceback

from bs4 import BeautifulSoup, Comment

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

tracking_folders = ["app", "biz"]

def track_haper_error(e: Exception):
    # Get the last (most recent) traceback entry from this project file
    tb = traceback.extract_tb(e.__traceback__)
    for t in tb[::-1]:
        file_name, line_number, func_name, text = t
        for folder in tracking_folders:
            if file_name.startswith(os.path.join(PROJECT_DIR, folder)):
                return file_name, line_number, func_name, text

    file_name, line_number, func_name, text = tb[-1]
    return file_name, line_number, func_name, text


def split_email_str(email_str):
    match = re.match(r"(.+?)\s*<(.+?)>", email_str)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return None, None


def extract_visible_text_from_email(html_content: str) -> str:
    # Parse HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script, style, head, meta, and other non-visible tags
    for tag in soup(["script", "style", "head", "meta", "title", "noscript"]):
        tag.decompose()

    # Optionally, remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Extract and return visible text
    text = soup.get_text(strip=True, separator="\n")

    # Normalize whitespace: remove extra blank lines and spaces
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)