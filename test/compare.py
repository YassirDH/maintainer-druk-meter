"""
Maintainer Pressure Meter: honest test
======================================

Compares my 50 hand labels (test/labels_manual.csv) with three methods:

  1. Model 1    cardiffnlp/twitter-roberta-base-sentiment-latest
                The model the meter uses live. English, trained on tweets.
  2. Model 2    cardiffnlp/twitter-xlm-roberta-base-sentiment
                Same kind of training, but multilingual (8 languages).
  3. Word list  A simple hand-written list of positive and negative words
                (see WORDLIST below). No AI: this is the floor.

Output:
  test/test_table.csv   per comment: my label, every method's verdict, where they disagree
  test/report.md        scores, confusion matrices, every model-1 error, jargon probe, xz look-back

Runs on GitHub (.github/workflows/compare.yml) as soon as
test/labels_manual.csv is uploaded. Locally: python test/compare.py
"""

import csv
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
LABEL_FILES = [HERE / "labels_manual.csv", HERE / "labels_handmatig.csv"]  # second = older name
TABLE_PATH = HERE / "test_table.csv"
REPORT_PATH = HERE / "report.md"

MODEL_1 = "cardiffnlp/twitter-roberta-base-sentiment-latest"
MODEL_2 = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
CLASSES = ["negative", "neutral", "positive"]

# --- Method 3: word list ----------------------------------------------------
# Deliberately general words, NOT tuned to programmers, to show what you get
# without AI. A word right after "not/no/never/don't..." counts the other way.

WORDLIST = {
    "positive": """
        thank thanks thx appreciate appreciated great awesome amazing excellent
        nice good love perfect brilliant helpful happy glad cool fantastic
        wonderful works worked working fixed solved congrats congratulations
        kudos lgtm beautiful clean elegant impressive welcome agree +1
    """.split(),
    "negative": """
        bad terrible awful horrible broken worse worst annoying frustrating
        frustrated disappointed disappointing useless ridiculous unacceptable
        hate stupid wrong fail fails failed failing failure crash crashes
        crashed error errors bug bugs buggy issue problem problems regression
        unfortunately sadly slow ugly mess confusing confused painful still
    """.split(),
}
NEGATORS = {"not", "no", "never", "don't", "doesn't", "didn't", "isn't",
            "wasn't", "can't", "cannot", "won't", "without", "nothing"}


def wordlist_predict(text):
    words = re.findall(r"[a-z+']+[0-9]?", text.lower())
    score = 0
    for i, w in enumerate(words):
        sign = 1 if w in WORDLIST["positive"] else -1 if w in WORDLIST["negative"] else 0
        if sign and any(p in NEGATORS for p in words[max(0, i - 3):i]):
            sign = -sign
        score += sign
    label = "positive" if score > 0 else "negative" if score < 0 else "neutral"
    return {"label": label, "score": score}


# --- Methods 1 and 2: Hugging Face models -----------------------------------

def normalise(label):
    l = label.lower()
    if l.startswith("neg") or l == "label_0":
        return "negative"
    if l.startswith("neu") or l == "label_1":
        return "neutral"
    if l.startswith("pos") or l == "label_2":
        return "positive"
    raise ValueError(f"Unknown label: {label}")


def model_predict(model_name, texts, batch_size=8):
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name).eval()
    names = [normalise(model.config.id2label[i]) for i in range(model.config.num_labels)]
    out = []
    for i in range(0, len(texts), batch_size):
        enc = tok(texts[i:i + batch_size], padding=True, truncation=True,
                  max_length=512, return_tensors="pt")
        with torch.no_grad():
            probs = torch.softmax(model(**enc).logits, dim=-1).tolist()
        for p in probs:
            d = dict(zip(names, p))
            label = max(d, key=d.get)
            out.append({"label": label, "confidence": round(d[label], 3)})
    return out


# --- Statistics (no extra packages, so every step can be followed) ---------

def confusion(truth, pred):
    m = {t: Counter() for t in CLASSES}
    for t, p in zip(truth, pred):
        m[t][p] += 1
    return m


def scores(truth, pred):
    n = len(truth)
    acc = sum(t == p for t, p in zip(truth, pred)) / n
    per_class = {}
    for c in CLASSES:
        tp = sum(t == c and p == c for t, p in zip(truth, pred))
        fp = sum(t != c and p == c for t, p in zip(truth, pred))
        fn = sum(t == c and p != c for t, p in zip(truth, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[c] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(CLASSES)
    return {"accuracy": acc, "macro_f1": macro_f1, "per_class": per_class}


def pct(x):
    return f"{100 * x:.0f}%"


def short(text, n=280):
    text = text.replace("|", "/").replace("\n", " ")
    return text if len(text) <= n else text[:n].rstrip() + "…"


# --- Jargon probe -----------------------------------------------------------
# Made-up sentences (not from the stream) that target the exact risk:
# technical words that sound negative in everyday language.

JARGON_PROBE = [
    ("Kill the process and restart the daemon, then it works.", "neutral"),
    ("This fixes a fatal error in the parser.", "positive"),
    ("The test suite crashes on ARM, here is the backtrace.", "neutral"),
    ("Deprecated in 3.12 and removed in 3.14.", "neutral"),
    ("Thanks, this was a terrible bug and your patch solves it!", "positive"),
    ("Abort the build if the checksum doesn't match.", "neutral"),
    ("Third time I'm asking. Is anyone actually maintaining this?", "negative"),
    ("Great, another release that breaks my setup. Well done.", "negative"),
]

# --- xz look-back -----------------------------------------------------------
# The real 2022 messages with which (probably fake) accounts pressured the xz
# maintainer, two years before the backdoor (CVE-2024-3094).
# Source: Russ Cox, https://research.swtch.com/xz-timeline

XZ_RETRO = [
    ("2022-04-22", "Jigar Kumar", "Patches spend years on this mailing list. There is no reason to think anything is coming soon."),
    ("2022-05-27", "Jigar Kumar", "Over 1 month and no closer to being merged. Not a surprise."),
    ("2022-06-07", "Jigar Kumar", "Progress will not happen until there is new maintainer."),
    ("2022-06-14", "Jigar Kumar", "With your current rate, I very doubt to see 5.4.0 release this year."),
    ("2022-06-21", "Dennis Ens", "I am sorry about your mental health issues, but its important to be aware of your own limits."),
    ("2022-06-22", "Jigar Kumar", "Why can't you commit this yourself?"),
]


# --- Main -------------------------------------------------------------------

def main():
    path = next((p for p in LABEL_FILES if p.exists()), None)
    if path is None:
        raise SystemExit("No label file found: upload test/labels_manual.csv")
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("my_label") in CLASSES]
    if not rows:
        raise SystemExit(f"No labels found in {path}")
    texts = [r["text"] for r in rows]
    truth = [r["my_label"] for r in rows]

    print(f"Read {len(rows)} labelled comments from {path.name}")
    m1 = model_predict(MODEL_1, texts)
    print("model 1 done")
    m2 = model_predict(MODEL_2, texts)
    print("model 2 done")
    wl = [wordlist_predict(t) for t in texts]

    methods = {
        "Model 1 (twitter-roberta, live)": [p["label"] for p in m1],
        "Model 2 (xlm-roberta, multilingual)": [p["label"] for p in m2],
        "Word list (no AI)": [p["label"] for p in wl],
    }

    # Test table
    with TABLE_PATH.open("w", encoding="utf-8", newline="") as f:
        fields = ["comment_id", "repo", "text", "my_label", "note",
                  "model1", "model1_conf", "model2", "model2_conf",
                  "wordlist", "wordlist_score",
                  "model1_correct", "model2_correct", "wordlist_correct", "disagreement"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r, a, b, c in zip(rows, m1, m2, wl):
            w.writerow({
                "comment_id": r["comment_id"], "repo": r["repo"], "text": r["text"],
                "my_label": r["my_label"], "note": r.get("note", ""),
                "model1": a["label"], "model1_conf": a["confidence"],
                "model2": b["label"], "model2_conf": b["confidence"],
                "wordlist": c["label"], "wordlist_score": c["score"],
                "model1_correct": a["label"] == r["my_label"],
                "model2_correct": b["label"] == r["my_label"],
                "wordlist_correct": c["label"] == r["my_label"],
                "disagreement": len({r["my_label"], a["label"], b["label"], c["label"]}) > 1,
            })

    # Report
    L = []
    L.append("# Test report: how often is the model right?\n")
    L.append(f"*{len(rows)} comments from the live stream, labelled blind (the model's verdict was hidden while labelling). "
             f"Sample: random, at most 10 per project, seed 42, bot commands excluded.*\n")
    dist = Counter(truth)
    L.append("**My labels:** " + ", ".join(f"{c} {dist[c]}" for c in CLASSES) + "\n")

    L.append("## Overview\n")
    L.append("| Method | Agrees with me | Macro-F1 | Negatives caught (recall) | Flagged negative and correct (precision) |")
    L.append("|---|---|---|---|---|")
    all_scores = {}
    for name, pred in methods.items():
        s = scores(truth, pred)
        all_scores[name] = s
        neg = s["per_class"]["negative"]
        L.append(f"| {name} | {pct(s['accuracy'])} | {s['macro_f1']:.2f} | {pct(neg['recall'])} | {pct(neg['precision'])} |")
    base = dist.most_common(1)[0]
    L.append(f"| *Always say '{base[0]}'* | {pct(base[1] / len(truth))} | – | – | – |")
    L.append("\n*Agrees with me* = share of comments where the method gives the same label as I did. "
             "*Macro-F1* = average over the three classes, so a method cannot score well by always saying 'neutral'. "
             "*Negatives caught* matters most for the user: how many of the truly negative comments does the meter pick up?\n")

    L.append("## Confusion matrices\n")
    L.append("Rows = my label, columns = what the method said.\n")
    for name, pred in methods.items():
        m = confusion(truth, pred)
        L.append(f"**{name}**\n")
        L.append("| me \\ method | " + " | ".join(CLASSES) + " |")
        L.append("|---|---|---|---|")
        for t in CLASSES:
            L.append(f"| **{t}** | " + " | ".join(str(m[t][p]) for p in CLASSES) + " |")
        L.append("")

    L.append("## Every error of model 1\n")
    L.append("Pick the three (or more) to explain in the README from here. The note is what I wrote while labelling.\n")
    L.append("| # | Project | Comment | Me | Model 1 (confidence) | Model 2 | Word list | Note |")
    L.append("|---|---|---|---|---|---|---|---|")
    k = 0
    for r, a, b, c in zip(rows, m1, m2, wl):
        if a["label"] != r["my_label"]:
            k += 1
            L.append(f"| {k} | {r['repo']} | {short(r['text'])} | {r['my_label']} | "
                     f"{a['label']} ({pct(a['confidence'])}) | {b['label']} | {c['label']} | {r.get('note', '')} |")
    if not k:
        L.append("| – | – | Model 1 made no errors | | | | | |")
    L.append("")

    probe_texts = [t for t, _ in JARGON_PROBE]
    p1, p2 = model_predict(MODEL_1, probe_texts), model_predict(MODEL_2, probe_texts)
    pw = [wordlist_predict(t) for t in probe_texts]
    L.append("## Jargon probe (made-up sentences, not from the stream)\n")
    L.append("Technical language that sounds negative in everyday English. Does the model read the tone or the words?\n")
    L.append("| Sentence | Intended | Model 1 | Model 2 | Word list |")
    L.append("|---|---|---|---|---|")
    for (t, want), a, b, c in zip(JARGON_PROBE, p1, p2, pw):
        mark = lambda x: f"{x} {'✓' if x == want else '✗'}"
        L.append(f"| {t} | {want} | {mark(a['label'])} | {mark(b['label'])} | {mark(c['label'])} |")
    L.append("")

    xz_texts = [t for _, _, t in XZ_RETRO]
    x1, x2 = model_predict(MODEL_1, xz_texts), model_predict(MODEL_2, xz_texts)
    xw = [wordlist_predict(t) for t in xz_texts]
    L.append("## xz look-back: would the meter have seen the pressure?\n")
    L.append("The real 2022 messages with which (probably fake) accounts pressured the sole xz maintainer, "
             "two years before the backdoor CVE-2024-3094. Source: [Russ Cox, xz timeline](https://research.swtch.com/xz-timeline). "
             "Intended label: negative (pressure on the maintainer).\n")
    L.append("| Date | Account | Message | Model 1 | Model 2 | Word list |")
    L.append("|---|---|---|---|---|---|")
    for (date, who, t), a, b, c in zip(XZ_RETRO, x1, x2, xw):
        L.append(f"| {date} | {who} | {t} | {a['label']} ({pct(a['confidence'])}) | {b['label']} | {c['label']} |")
    hits = sum(a["label"] == "negative" for a in x1)
    L.append(f"\nModel 1 flags **{hits} of the {len(XZ_RETRO)}** messages as negative. "
             "Note: these messages were posted on a mailing list, not on GitHub, so the meter would not have seen them at all.\n")

    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")
    for name, s in all_scores.items():
        print(f"{name}: {pct(s['accuracy'])} agreement, macro-F1 {s['macro_f1']:.2f}")
    print(f"Written: {TABLE_PATH} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
