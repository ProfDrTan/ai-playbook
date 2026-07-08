#!/usr/bin/env python3
"""
Content-drip pilot: pulls the next un-drafted AI Playbook chapter,
condenses it into a short LinkedIn-style post via Claude, and writes
the result to content-drip/drafts/ for manual review and posting.

Nothing here auto-posts anywhere. Output is a draft file only.
Uses claude-haiku-4-5-20251001 deliberately -- this is a short
condensing task, not a task that benefits from a larger model,
so the cheapest capable model is used to keep weekly token cost minimal.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(REPO_ROOT, "queue.json")
INDEX_PATH = os.path.join(os.path.dirname(REPO_ROOT), "index.html")
DRAFTS_DIR = os.path.join(REPO_ROOT, "drafts")

CHAPTER_ID_PATTERN = re.compile(r'id="(ch\d+)"')


def load_queue():
    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue):
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
        f.write("\n")


def extract_chapter_text(chapter_id):
    """Pull the raw HTML slice for one chapter, bounded by the next chX id."""
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    matches = list(CHAPTER_ID_PATTERN.finditer(html))
    start_idx = None
    end_pos = len(html)
    for i, m in enumerate(matches):
        if m.group(1) == chapter_id:
            start_idx = m.start()
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            break
    if start_idx is None:
        raise ValueError(f"Chapter id {chapter_id} not found in index.html")

    chunk = html[start_idx:end_pos]
    # Strip tags to plain text; good enough for summarization input.
    text = re.sub(r"<[^>]+>", " ", chunk)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def call_claude(chapter_title, chapter_text):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY secret not set in repo settings.")
        sys.exit(1)

    prompt = (
        f"Condense the following book chapter excerpt, titled "
        f"'{chapter_title}', into a single LinkedIn-style post of "
        f"150-200 words. Practical, tactics-focused tone. No hashtags, "
        f"no emoji, no markdown formatting -- plain text only, since "
        f"this will be copy-pasted directly into a LinkedIn post box.\n\n"
        f"Chapter excerpt:\n{chapter_text[:6000]}"
    )

    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return "".join(
        block.get("text", "") for block in data.get("content", [])
        if block.get("type") == "text"
    ).strip()


def main():
    queue = load_queue()
    next_item = next((i for i in queue["items"] if i["status"] == "pending"), None)

    if next_item is None:
        print("No pending chapters left in queue. Nothing to do.")
        return

    chapter_text = extract_chapter_text(next_item["id"])
    draft_text = call_claude(next_item["title"], chapter_text)

    os.makedirs(DRAFTS_DIR, exist_ok=True)
    filename = f"{date.today().isoformat()}-{next_item['id']}.md"
    draft_path = os.path.join(DRAFTS_DIR, filename)

    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(f"# Draft for {next_item['title']} ({next_item['id']})\n\n")
        f.write(f"Generated: {date.today().isoformat()}\n")
        f.write("Status: awaiting manual review before posting\n\n")
        f.write("---\n\n")
        f.write(draft_text)
        f.write("\n")

    next_item["status"] = "drafted"
    next_item["draft_file"] = f"content-drip/drafts/{filename}"
    save_queue(queue)

    print(f"Draft written: {draft_path}")


if __name__ == "__main__":
    main()
