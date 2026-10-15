# Malaysia Daily Brief

Every hour, GitHub runs a small Python script that pulls the last 24 hours of headlines from Malaysian news outlets, removes stories that several outlets ran, and publishes a clean one-page brief you can open on your phone.

## How it works

```
GitHub Actions (every hour, at 17 past)
        │
        ▼
digest.py reads feeds.yml ──► fetches RSS feeds ──► drops old and duplicate stories
        │
        ▼
writes docs/index.html (today), docs/YYYY-MM-DD.html (archive), digests/YYYY-MM-DD.md
        │
        ▼
commits them back to the repo ──► GitHub Pages serves docs/ as a website
```

| File | What it does |
|---|---|
| `feeds.yml` | The news sources and sections. This is the only file you need to edit day to day. |
| `digest.py` | Fetches, filters, deduplicates and writes the brief. |
| `.github/workflows/daily-brief.yml` | The schedule. Tells GitHub when to run the script and to save the result. |
| `docs/` | The website. Created by the first run. |
| `digests/` | A Markdown copy of each day's brief, readable directly on github.com. The day's file is updated every hour. |

## One-time setup

1. Push this folder to a new **public** GitHub repository. (Free GitHub accounts can only publish Pages sites from public repos. The brief only contains public headlines, so nothing sensitive is exposed.)
2. Go to the repo's **Actions** tab, pick **Daily news brief**, and click **Run workflow**. Wait about a minute for it to finish.
3. Go to **Settings → Pages**. Under "Build and deployment", choose **Deploy from a branch**, branch **main**, folder **/docs**, and save.
4. After a minute your brief is live at `https://<your-username>.github.io/<repo-name>/`. Bookmark it on your phone.

## Changing what you get

Edit `feeds.yml` on github.com (click the file, then the pencil icon) and commit. The next run picks it up. You can:

1. Add or remove an outlet: add a `name` and `url` under any section.
2. Add a section: copy an existing section block and give it a new name.
3. Track a topic: Google News builds a feed for any search. Change the `q=` part of a Google News URL, for example `q=Malaysia+semiconductor+when:1d`.
4. Change how many stories show: edit `max_items`.

## Running it yourself

```bash
pip install -r requirements.txt
python digest.py
open docs/index.html
```

## Good to know

1. **Some feeds fail on some days.** The Star and FMT sometimes block automated readers. The script skips any feed that doesn't respond and lists it at the bottom of the brief. If every feed fails, the run fails, the old brief stays up, and GitHub emails you.
2. **GitHub's schedule is approximate.** Runs can start 5 to 30 minutes late when GitHub is busy.
3. **Scheduled runs stop after 60 days of no activity in a repo.** The daily commit counts as activity, so this keeps itself alive.
4. **Feed content is treated as untrusted.** All HTML from feeds is stripped and escaped, and only `http(s)` links are kept, so a compromised feed can't inject scripts into your page.
