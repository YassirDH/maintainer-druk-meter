"""
Maintainer Pressure Meter: collector
====================================

What this script does every time it runs:
  1. For every repo in repos.txt: fetch the issue and PR comments posted since
     the previous run (GitHub REST API).
  2. Drop bots, slash commands, bot commands and very short comments; strip
     code, logs, links, quotes and @mentions from the text.
  3. Let a pre-trained Hugging Face transformer score the sentiment.
  4. Append the new rows to data/comments.csv, with timestamps.

It runs on its own every 15 minutes via GitHub Actions
(see .github/workflows/collect.yml). Locally: python collect.py
"""

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# --- Settings ---------------------------------------------------------------

MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"

DATA_DIR = Path("data")
CSV_PATH = DATA_DIR / "comments.csv"
STATE_PATH = DATA_DIR / "state.json"
REPOS_PATH = Path("repos.txt")

FIRST_RUN_LOOKBACK = timedelta(hours=1)   # first run: only the last hour
OVERLAP = timedelta(minutes=10)           # small overlap; duplicates are skipped
MAX_PAGES = 5                             # at most 5 x 100 comments per repo per run
MIN_CHARS = 20                            # shorter comments say too little

# Bots that do not register as type "Bot" on GitHub
KNOWN_BOTS = {
    "k8s-ci-robot", "k8s-triage-robot", "rustbot", "rust-timer", "bors",
    "rust-log-analyzer", "nodejs-github-bot", "bedevere-bot",
    "python-cla-bot", "gopherbot",
}

FIELDS = [
    "comment_id", "repo", "created_at", "collected_at",
    "author_hash", "author_role", "is_pull_request",
    "text", "label", "score", "p_negative", "p_neutral", "p_positive",
    "url", "model",
]

SALT = os.environ.get("HASH_SALT", "")


# --- Helpers ----------------------------------------------------------------

def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def to_iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def read_repos():
    lines = REPOS_PATH.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def seen_ids():
    if not CSV_PATH.exists():
        return set()
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        return {row["comment_id"] for row in csv.DictReader(f)}


def author_hash(login):
    """Never store the username, only a pseudonym: this lets us see whether one
    account moves the line without knowing who it is. The secret salt
    (HASH_SALT) prevents anyone from hashing usernames to reverse it."""
    return hashlib.sha256((SALT + login).encode("utf-8")).hexdigest()[:12]


def is_bot(user):
    user = user or {}
    login = (user.get("login") or "").lower()
    return user.get("type") == "Bot" or login.endswith("[bot]") or login in KNOWN_BOTS


def clean(body):
    """Turn a GitHub comment into plain text the model can read."""
    t = body or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)              # code blocks
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)             # template comments
    t = re.sub(r"<details>.*?</details>", " ", t, flags=re.S | re.I)  # collapsed logs
    t = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith(">"))  # quotes
    t = re.sub(r"`[^`]*`", " ", t)                            # inline code
    t = re.sub(r"https?://\S+", "http", t)                    # links (as the model card prescribes)
    t = re.sub(r"(?<![\w.])@[A-Za-z0-9-]+", "@user", t)       # @mentions removed (privacy)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# Instructions people type to a bot ("@bors r+", "@bors try jobs=...").
# Not an opinion, so not counted. Found in the first 48 hours of data (~5%, mostly Rust).
BOT_COMMAND = re.compile(
    r"^(thanks!?\s+)?@user\s+(r\+|r-|r=|try|rollup|queue|delegate|retry|p=|"
    r"add-label|remove-label|label|ping|proposal cancelled)", re.I)


def keep(text):
    if len(text) < MIN_CHARS:
        return False
    if text.startswith("/"):        # commands such as /retest, /lgtm, /assign
        return False
    if BOT_COMMAND.match(text):
        return False
    return True


# --- Fetching ---------------------------------------------------------------

def fetch_repo(session, repo, since):
    """All comments created or edited since `since`, oldest first.
    Returns (comments, hit_page_limit)."""
    url = f"https://api.github.com/repos/{repo}/issues/comments"
    params = {"since": to_iso(since), "sort": "updated", "direction": "asc", "per_page": 100}
    comments = []
    for _ in range(MAX_PAGES):
        r = session.get(url, params=params, timeout=30)
        if r.status_code != 200:
            print(f"  ! {repo}: HTTP {r.status_code} {r.text[:120]}")
            return comments, False
        comments.extend(r.json())
        next_url = r.links.get("next", {}).get("url")
        if not next_url:
            return comments, False
        url, params = next_url, None
    return comments, True


# --- Sentiment --------------------------------------------------------------

class SentimentModel:
    """Loads the Hugging Face model and returns, per text, the probability of
    negative / neutral / positive."""

    def __init__(self):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME).eval()
        cfg = self.model.config
        self.labels = [cfg.id2label[i].lower() for i in range(cfg.num_labels)]

    def predict(self, texts, batch_size=16):
        out = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            enc = self.tokenizer(batch, padding=True, truncation=True,
                                 max_length=512, return_tensors="pt")
            with self.torch.no_grad():
                probs = self.torch.softmax(self.model(**enc).logits, dim=-1).tolist()
            out.extend(dict(zip(self.labels, p)) for p in probs)
        return out


# --- Main -------------------------------------------------------------------

def main():
    DATA_DIR.mkdir(exist_ok=True)
    if not SALT:
        print("Warning: HASH_SALT is not set; author hashes could be reversed.")

    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["User-Agent"] = "maintainer-pressure-meter"
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        session.headers["Authorization"] = f"Bearer {token}"

    state = load_state()
    already = seen_ids()
    run_start = now_utc()
    new_rows = []

    for repo in read_repos():
        since = from_iso(state[repo]) - OVERLAP if repo in state else run_start - FIRST_RUN_LOOKBACK
        comments, hit_limit = fetch_repo(session, repo, since)

        kept = 0
        for c in comments:
            cid = str(c["id"])
            if cid in already or is_bot(c.get("user")):
                continue
            if from_iso(c["created_at"]) < since:   # old comment that was only edited
                continue
            text = clean(c.get("body"))
            if not keep(text):
                continue
            user = c.get("user") or {}
            new_rows.append({
                "comment_id": cid,
                "repo": repo,
                "created_at": c["created_at"],
                "collected_at": to_iso(run_start),
                "author_hash": author_hash(user.get("login", "")),
                "author_role": c.get("author_association", ""),
                "is_pull_request": "/pull/" in c.get("html_url", ""),
                "text": text,
                "url": c.get("html_url", ""),
                "model": MODEL_NAME,
            })
            already.add(cid)
            kept += 1

        # Next run continues from here. If we hit the page limit, continue from
        # the last comment we saw, so nothing is missed.
        if hit_limit and comments:
            state[repo] = comments[-1]["updated_at"]
        else:
            state[repo] = to_iso(run_start)
        print(f"  {repo}: {len(comments)} fetched, {kept} new")

    if new_rows:
        model = SentimentModel()
        for row, p in zip(new_rows, model.predict([r["text"] for r in new_rows])):
            row["p_negative"] = round(p["negative"], 4)
            row["p_neutral"] = round(p["neutral"], 4)
            row["p_positive"] = round(p["positive"], 4)
            row["score"] = round(p["positive"] - p["negative"], 4)   # from -1 to +1
            row["label"] = max(("negative", "neutral", "positive"), key=lambda k: p[k])

        write_header = not CSV_PATH.exists()
        with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerows(new_rows)

    save_state(state)
    print(f"Done: {len(new_rows)} new comments saved.")


if __name__ == "__main__":
    main()
