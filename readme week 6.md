# Maintainer Pressure Meter

**A sentiment meter that continuously reads along in the GitHub comments of the open-source projects our digital infrastructure runs on, so a fund can see where pressure on maintainers is building up.**

- **Live dashboard:** https://yassirdh.github.io/maintainer-druk-meter/
- **Test report:** [test/report.md](test/report.md) · **Test table:** [test/test_table.csv](test/test_table.csv)
- **Collected data:** [data/comments.csv](data/comments.csv)
- Hackathon 6 "Live Pulse" · SDG 9 · by Yassir

---

## 1. The problem

Almost all software, from government login services to your banking app, runs on open-source components. Many of those components are maintained by one person or a handful of people, often unpaid.

**xz-utils** showed what can go wrong. In 2022 its sole maintainer, Lasse Collin, received messages from unknown accounts such as *"Progress will not happen until there is new maintainer"* and *"With your current rate, I very doubt to see 5.4.0 release this year."* He replied that his *"ability to care has been fairly limited mostly due to longterm mental health issues"*. Not long after, a new helper, "Jia Tan", was given more access. In 2024 it turned out that this person had built a backdoor into xz, which was discovered just before it reached stable Linux distributions (CVE-2024-3094). Pressure on an overloaded maintainer was part of the attack. ([Russ Cox, xz timeline](https://research.swtch.com/xz-timeline); [CSO Online](https://www.csoonline.com/article/2077692/dangerous-xz-utils-backdoor-was-the-result-of-years-long-supply-chain-compromise-effort.html))

It is not an exception. In Tidelift's survey of maintainers, **58%** say they have quit a project (22%) or considered quitting (36%); **44%** of them name burnout as a reason. ([Tidelift 2023 maintainer report, via DEV](https://dev.to/tidelift/maintainer-burnout-is-real-almost-60-of-maintainers-have-quit-or-considered-quitting-maintaining-one-of-their-projects-51ma))

**What goes wrong today?** Funds that support maintainers cannot read thousands of issue threads. They hear about an overloaded project only when someone quits, or when it makes the news.

## 2. User and decision

**Who reads the meter:** a programme officer at a fund that supports maintainers, such as Germany's **Sovereign Tech Agency** (which, through the [Sovereign Tech Fellowship](https://sovereign.tech/programs/fellowship), pays maintainers of critical projects directly) or the Dutch **NLnet** foundation ([NGI Zero](https://www.nlnet.nl/NGI0)).

**What they do with it:** every week, look at which projects stand out (many negative comments, lots of pressure from outsiders, or one account that keeps coming back), read those comments themselves, and decide which project to **contact** or **offer support** to (a fellowship, funding for an extra maintainer, help with moderation). The meter decides nothing on its own: it points to where a human should go and read.

**Whose voices are in the stream:** developers, users and maintainers who write in English in public GitHub issues and pull requests. In the first 48 hours: 1,688 comments from 727 different accounts, 64% of them from outsiders (not members of the project team).

**Who is missing:**
- Projects that do not work on GitHub. **xz and zlib produced zero comments in 48 hours.** The pressure on xz in 2022 was on a mailing list; this meter would never have seen it.
- Private messages, email, chat (Discord, IRC, Matrix). That is often where the heaviest pressure lands.
- Non-English speakers, and people who do not dare to comment in a public issue.
- People who have already given up. A quiet project can also mean everyone has left.
- The end users of the infrastructure (citizens, hospitals) never write in these issues.

## 3. SDG 9: Industry, Innovation and Infrastructure

Open-source software is **digital infrastructure**: the roads and bridges of all other software. SDG target 9.1 calls for *reliable, sustainable and resilient infrastructure*. Here, that resilience depends on a handful of people. If they burn out, a component disappears or is taken over by the wrong person (xz). This meter helps maintenance funding reach the places where the load is highest.

## 4. The solution

```
GitHub REST API  ──►  collect.py  ──►  cleaning  ──►  Hugging Face model  ──►  data/comments.csv  ──►  index.html
 (15 projects)       (every 15 min,    (bots, code,    (twitter-roberta,        (timestamped,           (dashboard on
                     GitHub Actions)    logs, names)    3 labels)                hashed author)          GitHub Pages)
```

| Step | How | Where |
|---|---|---|
| **Stream** | New issue and PR comments from 15 critical projects (curl, OpenSSL, zlib, expat, xz, Log4j, requests, CPython, Node.js, Go, Rust, Kubernetes, NumPy, Home Assistant, Nextcloud) | `repos.txt` |
| **Fetch** | `GET /repos/{repo}/issues/comments?since=…`, per project from the previous run onwards (plus 10 min overlap; duplicates skipped). At most 500 per project per run; if that limit is hit, the next run continues where this one stopped. | `collect.py` |
| **Continuous** | GitHub Actions starts the collector every 15 minutes (GitHub sometimes delays or skips scheduled runs; 134 runs in the first 48 hours). Every run is a commit, so the history proves it ran continuously. | `.github/workflows/collect.yml` |
| **Cleaning** | Removed: bots (GitHub type "Bot", `[bot]` names, known bot accounts), slash commands (`/retest`), bot commands typed by people (`@bors r+`, ~5% of the raw data, mostly Rust), comments under 20 characters, code blocks, collapsed logs, quotes, inline code. Links become `http`, @mentions become `@user` (as the model card prescribes, and for privacy). | `collect.py` → `clean()`, `keep()` |
| **Model** | `cardiffnlp/twitter-roberta-base-sentiment-latest`, run locally with `transformers` (no API). Per comment, the probability of negative/neutral/positive; label = highest probability; score = P(positive) − P(negative). | `collect.py` → `SentimentModel` |
| **Storage** | CSV with time posted and time collected, project, the writer's role (`author_association`), hashed author, cleaned text, label, probabilities, link, model name | `data/comments.csv` |
| **View** | Dashboard: % negative/positive per hour, 3 hours, 6 hours or day; number of comments underneath; clicking a period shows the comments behind it; a table per project with signals | `index.html` |

**Why this model?** GitHub comments look more like tweets than like reviews or news: short, informal, with abbreviations and emoji. This model was trained on tweets, has a **neutral** label (most comments are matter-of-fact) and is one of the most widely used sentiment models on Hugging Face. Its weakness, that it does not know programmer language, is exactly what the test examines.

### Model card summary

| | Model 1 (live) | Model 2 (comparison) |
|---|---|---|
| Name | [cardiffnlp/twitter-roberta-base-sentiment-latest](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest) | [cardiffnlp/twitter-xlm-roberta-base-sentiment](https://huggingface.co/cardiffnlp/twitter-xlm-roberta-base-sentiment) |
| Trained on | ~124 million tweets (Jan 2018 – Dec 2021), fine-tuned on TweetEval | ~198 million tweets, fine-tuned for sentiment in 8 languages |
| Languages | English | Arabic, English, French, German, Hindi, Italian, Spanish, Portuguese |
| Labels | negative, neutral, positive | negative, neutral, positive |
| Licence | CC BY 4.0 | not stated on the model card |
| Paper | TimeLMs (arXiv 2202.03829) | XLM-T, LREC 2022 (arXiv 2104.12250) |

Plus a **word list without AI** (~50 positive and ~50 negative general English words, with simple negation) as the floor. See `WORDLIST` in `test/compare.py`.

## 5. Honest test

**Method.** 50 comments from the live stream, chosen at random (at most 10 per project, fixed seed 42, bot commands excluded) and **labelled blind**: the model's verdict was hidden while labelling (`test/label.html`). Rule: judge the tone of the writer, not the topic. The same 50 go through model 1, model 2 and the word list (`test/compare.py`, run by `.github/workflows/compare.yml`).

**Results** (full details, confusion matrices and every error in [test/report.md](test/report.md); per comment in [test/test_table.csv](test/test_table.csv)). My labels: 14 negative, 27 neutral, 9 positive.

| Method | Agrees with me | Negatives caught (recall) | Flagged negative and correct (precision) | Macro-F1 |
|---|---|---|---|---|
| **Model 1** (twitter-roberta, live) | **72%** (36/50) | 71% (10/14) | **77%** (10/13) | **0.66** |
| Model 2 (xlm-roberta, multilingual) | 64% (32/50) | 79% (11/14) | 55% (11/20) | 0.63 |
| Word list (no AI) | 38% (19/50) | 29% (4/14) | 36% (4/11) | 0.36 |
| *Always say "neutral"* | 54% | 0% | – | – |

What this shows:
- **Model 1 agrees with me on 72%** of the comments, clearly above the 54% you would get by always saying "neutral". When it calls a comment negative, it is right 77% of the time.
- **Its weak spot is positive comments:** it recognised only 3 of my 9 positive comments. Gratitude in a technical message ("Thanks for spotting this! … it's a regression") is pulled back to neutral by the technical words around it.
- **Model 2 catches one more negative comment, but raises far more false alarms:** it called 9 of my 27 neutral comments negative (model 1: 3). On the dashboard that would show about 1.5 times as many negative comments.
- **The word list is worse than doing nothing** (38% vs 54%): words like *issue*, *error* and *bug* are everywhere in a bug tracker and say nothing about tone.
- **Caveat:** 50 comments, of which 14 negative, is a small test. The difference between 10 and 11 negatives caught is one comment. The numbers show a direction, not a precise score.

### Three failures explained

1. **Jargon read as emotion.** *"Behavior 2 seems likely to cause issues for code like this, which I have written:"* (rust-lang/rust). Me: neutral · Model 1: **negative (74%)**. A calm technical observation; the model reacts to *cause issues*, which in tweets signals complaining but in a bug tracker is everyday vocabulary. Model 2 makes the same mistake.
2. **A mixed message: thanks plus a bug.** *"Thanks for spotting this! Reported upstream in isaacs/minimatch#329, it's a regression since 10.2.3."* (nodejs/node). Me: positive · Model 1: neutral (64%). The writer is grateful, but *regression* and the issue number pull the score to neutral. This is why the meter underestimates positive comments: appreciation in open source is usually wrapped in technical detail.
3. **Polite frustration is invisible.** *"May I propose we prioritize the search option? Finding the items without any apparent ordering is getting a real pita 😅 … I'd think a simple filter on top would do wonders."* (nextcloud/server). Me: negative · Model 1: neutral (56%) · Model 2: **positive**. *pita* is slang for "pain in the a**", softened by an emoji and a polite proposal. **Three of the four negative comments model 1 missed were polite requests like this** ("would you mind…", "would it be possible to add…"); the fourth was a calm refusal. Developers rarely shout; they phrase frustration as a request.

**The failure that taught me the most** goes against intuition: the only Italian comment in the sample (*"Io lo devo ancora provare, ma vedo che questo post ha chiuso anche il problema #184973"*, "I still have to try it, but I see this post also closed problem #184973") was labelled correctly by the **English-only** model 1 (neutral, 85%) and **wrongly by the multilingual** model 2 (negative), probably because of the word *problema*. "Multilingual" did not mean "better" on this stream.

Already visible in the collected data, outside the test (model 1):
- *"Wrt codecov, I don't think I can do something, codecov/patch is at 100% :shrug:"* → **negative (93%)**. The writer reports that test coverage is 100%; the model reads the shrug emoji and "can't do something".
- *"Playwright is still the unified search flaky failure. Restarting, else I'll force merge"* → **negative (91%)**. A routine status update; *flaky failure* is jargon for an unreliable test.
- *"Looks like rustc is broken since it produced no output."* → **negative (93%)**. A factual observation; *broken* refers to the compiler, not to a person.

The report also tests two things that do not come from the stream: a **jargon probe** (eight made-up sentences with technical words that sound negative in everyday English) and an **xz look-back** (the real 2022 pressure messages sent to the xz maintainer).

**Jargon probe** (made-up sentences): model 1 got only 2 of 8 right. *"Thanks, this was a terrible bug and your patch solves it!"* became negative, and the sarcastic *"Great, another release that breaks my setup. Well done."* became **positive** with all three methods.

**xz look-back:** model 1 flagged **5 of the 6** real pressure messages from 2022 as negative (model 2: 2 of 6, word list: 0 of 6). So the model *could* have recognised the pressure on xz. The problem was the stream: those messages were on a mailing list, which this meter does not read. **The model was ready; the data source was not.**

### Which method would I hand to the user?

**Model 1**, the one the meter already uses. It agrees with me most often (72%) and, more importantly for this user, its negative alarms are the most trustworthy (77% correct). A fund officer has limited time to read comments; model 2 would send them after three times as many false alarms (9 instead of 3) for one extra real negative, and they would soon stop trusting the dashboard. The word list should not be used at all.

But model 1 is not reliable enough to act on **on its own**: it misses polite frustration and misreads jargon. That is why the dashboard never shows a percentage without the number of comments, flags single accounts and small samples, and puts the actual comments one click away. The meter's job is to tell a human **where to start reading**, not what to decide.

## 6. Ethical reflection

**Who writes in this stream, and who never does?** This stream consists of English-speaking developers who dare to comment in a public issue. I do not see the heaviest pressure on maintainers (private messages, email, chat), nor projects outside GitHub: xz and zlib produced zero comments in 48 hours, and the messages that pressured xz in 2022 were on a mailing list. A calm dashboard therefore does not mean a project is doing well. It can also mean people have already given up, or that they talk somewhere else.

**What does the model misread?** The model was trained on tweets and reads programmer language literally: *broken*, *failure*, *kill*, *fatal* make a matter-of-fact comment negative (see the examples above). That makes a project where a lot of debugging happens look "angrier" than it is. Notably, comments from **maintainers themselves** are more often negative (21.5%) than those from outsiders (19.3%). A large part of what the model calls "negative" is technical frustration about bugs, not pressure from users on the team. The other way round, the test showed that the model misses **polite frustration**: three of the four negative comments it missed were phrased as a polite request ("would you mind…", "may I propose…"). Sarcasm fools it completely ("Well done." became positive), and the stream is not only English: the sample contained an Italian comment, which, surprisingly, the multilingual model got wrong.

**Can bots or one account move the line?** Yes. I filter out bots and bot commands (~5% of the raw data). The dashboard also shows, per project, what share of the negative comments comes from one and the same account. For curl and NumPy that was 36%: there, one person determines a sizeable part of the line.

**Privacy.** I do not store usernames, profiles or avatars. @mentions in the text become `@user`. Names can still slip through inside the text itself (for example a quoted email header such as "On Wed, Oct 14, [name] wrote:"); I did not try to remove those, because recognising names reliably needs another model. The author is stored as a **salted hash**: that lets me see whether one account keeps coming back without knowing who it is (the salt is a secret in GitHub, so the hash cannot be reversed by hashing usernames). The data does keep the link to the original comment so the user can read the context; whoever follows the link sees the name on GitHub. That is a deliberate trade-off: without context, the user cannot check the model's verdict. Under [GitHub's Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies) (section 7), researchers may use public information for research provided publications are open access, and using the information for spam or selling personal information is prohibited. This project is public and sells nothing.

**Which decision could go wrong?** If the fund trusts the line blindly, it could (1) send money to a project that is simply debugging a lot of bugs instead of to one where people are under pressure, (2) overlook a quiet, vulnerable project like xz, or (3) label a project or person as "toxic" based on a model that misreads jargon.

**What I did about it:**
- A **warning at the top of the dashboard** about jargon, missing voices and small numbers.
- **Counts next to every percentage**; periods with fewer than 10 comments are shown as hollow dots and dashed lines; projects with fewer than 30 comments get "too little data, no conclusion possible".
- The **comments behind every peak or dip** are one click away, so a human reads before anything is decided.
- A split between **maintainers and outsiders**, and a signal when **one account** dominates the negative comments.
- **No names**: @mentions replaced, authors only as a salted hash.
- **Bots and bot commands** filtered out.

## 7. What this must NOT be used for

- **Not to judge**, contact or rank individual people. The hash exists to detect a distortion, not to find someone.
- **Not as an automatic funding decision.** The meter points to where a human should read; it decides nothing.
- **Not to publicly label projects as "toxic"** or to compare them in a league table.
- **Not for moderation** (hiding comments, blocking people).
- **Not as proof that a project is healthy.** Quiet is not the same as fine.

## 8. How to run it

**On GitHub (how this project runs):**
1. Fork or copy this repo (public, so Actions minutes are free).
2. Settings → Secrets and variables → Actions → New repository secret: `HASH_SALT` = a long random string.
3. Actions → *Collect comments* → Run workflow. After that it starts every 15 minutes on its own.
4. Settings → Pages → *Deploy from a branch* → `main` / `(root)`. The dashboard is then at `https://<user>.github.io/<repo>/`.
5. To add or remove projects, edit `repos.txt`.

**Locally:**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
export HASH_SALT="something-secret"   # Windows: set HASH_SALT=something-secret
python collect.py                     # one run; repeat or schedule with cron / Task Scheduler
python -m http.server                 # open http://localhost:8000 for the dashboard
```

**Redo the test:** open `test/label.html`, choose `data/comments.csv`, label 50 comments, upload `test/labels_manual.csv`. The *Honest test* workflow runs `test/compare.py` and commits `test/test_table.csv` and `test/report.md`.

## 9. Files

| File | What |
|---|---|
| `collect.py` | Fetch, clean, score sentiment, store |
| `repos.txt` | The projects being followed |
| `.github/workflows/collect.yml` | Runs the collector every 15 minutes |
| `data/comments.csv` | All collected comments with sentiment and timestamps |
| `data/state.json` | Per project: how far it has been fetched |
| `index.html` | The dashboard |
| `test/label.html` | Tool for blind labelling |
| `test/labels_manual.csv` | My 50 labels |
| `test/compare.py` · `.github/workflows/compare.yml` | Comparison of three methods |
| `test/test_table.csv` · `test/report.md` | The test results |

## Sources

- Russ Cox, *Timeline of the xz open source attack*: https://research.swtch.com/xz-timeline
- CSO Online, *Dangerous XZ Utils backdoor was the result of years-long supply chain compromise effort*: https://www.csoonline.com/article/2077692/dangerous-xz-utils-backdoor-was-the-result-of-years-long-supply-chain-compromise-effort.html
- Tidelift, *2023 State of the Open Source Maintainer Report* (summary): https://dev.to/tidelift/maintainer-burnout-is-real-almost-60-of-maintainers-have-quit-or-considered-quitting-maintaining-one-of-their-projects-51ma
- Sovereign Tech Agency, *Sovereign Tech Fellowship*: https://sovereign.tech/programs/fellowship
- NLnet, *NGI Zero*: https://www.nlnet.nl/NGI0
- GitHub, *Acceptable Use Policies*: https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies
- Model cards: https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest · https://huggingface.co/cardiffnlp/twitter-xlm-roberta-base-sentiment
