"""
Maintainer-druk-meter — verzamelaar
===================================

Wat dit script doet, elke keer dat het draait:
  1. Voor elke repo in repos.txt: haal de issue- en PR-reacties op die sinds
     de vorige keer zijn geplaatst (GitHub REST API).
  2. Gooi bots, slash-commando's en te korte reacties weg; haal code, logs,
     links, citaten en @namen uit de tekst.
  3. Laat een pre-trained transformer van Hugging Face het sentiment bepalen.
  4. Voeg de nieuwe regels toe aan data/comments.csv, met tijdstempel.

Het draait elke 15 minuten vanzelf via GitHub Actions
(zie .github/workflows/collect.yml). Lokaal kan het ook: python collect.py
"""

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# --- Instellingen -----------------------------------------------------------

MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"

DATA_DIR = Path("data")
CSV_PATH = DATA_DIR / "comments.csv"
STATE_PATH = DATA_DIR / "state.json"
REPOS_PATH = Path("repos.txt")

FIRST_RUN_LOOKBACK = timedelta(hours=1)   # eerste keer: alleen het laatste uur
OVERLAP = timedelta(minutes=10)           # kleine overlap, dubbelen filteren we
MAX_PAGES = 5                             # max 5 x 100 reacties per repo per run
MIN_CHARS = 20                            # kortere reacties zeggen te weinig

# Bots die zich niet als "Bot" registreren bij GitHub
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


# --- Hulpfuncties -----------------------------------------------------------

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
    """Geen gebruikersnaam opslaan, wel een pseudoniem: zo kunnen we zien of
    één account de lijn beweegt, zonder te weten wie het is. Het geheime
    zout (HASH_SALT) voorkomt dat iemand de hash terugrekent naar de naam."""
    return hashlib.sha256((SALT + login).encode("utf-8")).hexdigest()[:12]


def is_bot(user):
    user = user or {}
    login = (user.get("login") or "").lower()
    return user.get("type") == "Bot" or login.endswith("[bot]") or login in KNOWN_BOTS


def clean(body):
    """Maak van een GitHub-reactie platte tekst die het model kan lezen."""
    t = body or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)              # codeblokken
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)             # template-commentaar
    t = re.sub(r"<details>.*?</details>", " ", t, flags=re.S | re.I)  # ingeklapte logs
    t = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith(">"))  # citaten
    t = re.sub(r"`[^`]*`", " ", t)                            # inline code
    t = re.sub(r"https?://\S+", "http", t)                    # links (zoals het modelkaartje voorschrijft)
    t = re.sub(r"(?<![\w.])@[A-Za-z0-9-]+", "@user", t)       # @namen weg (privacy)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def keep(text):
    if len(text) < MIN_CHARS:
        return False
    if text.startswith("/"):        # commando's als /retest, /lgtm, /assign
        return False
    return True


# --- Ophalen ----------------------------------------------------------------

def fetch_repo(session, repo, since):
    """Alle reacties die sinds `since` zijn geplaatst of bewerkt, oudste eerst.
    Geeft (reacties, raakte_limiet) terug."""
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
    """Laadt het Hugging Face-model en geeft per tekst de kans op
    negatief / neutraal / positief terug."""

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


# --- Hoofdprogramma ---------------------------------------------------------

def main():
    DATA_DIR.mkdir(exist_ok=True)
    if not SALT:
        print("Let op: HASH_SALT is niet gezet; auteur-hashes zijn dan terug te rekenen.")

    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["User-Agent"] = "maintainer-druk-meter"
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
            if from_iso(c["created_at"]) < since:   # oude reactie die alleen bewerkt is
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

        # Volgende keer verder vanaf hier. Als we de paginalimiet raakten,
        # gaan we verder vanaf de laatst geziene reactie, zodat we niets missen.
        if hit_limit and comments:
            state[repo] = comments[-1]["updated_at"]
        else:
            state[repo] = to_iso(run_start)
        print(f"  {repo}: {len(comments)} opgehaald, {kept} nieuw")

    if new_rows:
        model = SentimentModel()
        for row, p in zip(new_rows, model.predict([r["text"] for r in new_rows])):
            row["p_negative"] = round(p["negative"], 4)
            row["p_neutral"] = round(p["neutral"], 4)
            row["p_positive"] = round(p["positive"], 4)
            row["score"] = round(p["positive"] - p["negative"], 4)   # van -1 tot +1
            row["label"] = max(("negative", "neutral", "positive"), key=lambda k: p[k])

        write_header = not CSV_PATH.exists()
        with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerows(new_rows)

    save_state(state)
    print(f"Klaar: {len(new_rows)} nieuwe reacties opgeslagen.")


if __name__ == "__main__":
    main()
