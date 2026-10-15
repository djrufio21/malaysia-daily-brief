#!/usr/bin/env python3
"""Build a daily Malaysia news brief from RSS feeds.

Reads feeds.yml, pulls the last day's stories, removes duplicates across
outlets, and writes:
  docs/index.html          today's brief (the page GitHub Pages shows)
  docs/YYYY-MM-DD.html     a dated copy for the archive
  docs/archive.html        list of past briefs
  digests/YYYY-MM-DD.md    plain Markdown copy, readable on github.com
"""

import calendar
import datetime as dt
import difflib
import html
import re
import socket
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import yaml

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DIGESTS = ROOT / "digests"
MYT = ZoneInfo("Asia/Kuala_Lumpur")
USER_AGENT = "Mozilla/5.0 (compatible; MalaysiaDailyBrief/1.0)"
SIMILARITY = 0.82  # titles this similar are treated as the same story

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
# Bernama prefixes titles with a desk name, e.g. "General : ..."
DESK_PREFIX_RE = re.compile(r"^(General|World|Business|Sports|Politics|Features|Bernama)\s*:\s*", re.I)

socket.setdefaulttimeout(20)


def clean_text(raw):
    """Strip HTML tags and entities from feed text so nothing executable reaches the page."""
    text = TAG_RE.sub(" ", raw or "")
    text = html.unescape(html.unescape(text))  # some feeds double-encode
    return SPACE_RE.sub(" ", text).strip()


def shorten(text, limit=220):
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def norm_title(title):
    return re.sub(r"[^a-z0-9 ]", "", title.lower())


def entry_time(entry):
    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    if not stamp:
        return None
    return dt.datetime.fromtimestamp(calendar.timegm(stamp), tz=dt.timezone.utc)


def fetch_feed(feed):
    """Return (stories, error). A feed that fails returns an error instead of raising."""
    try:
        parsed = feedparser.parse(feed["url"], agent=USER_AGENT)
    except Exception as exc:  # network errors, timeouts
        return [], f"{type(exc).__name__}: {exc}"

    status = parsed.get("status", 200)
    if status >= 400:
        return [], f"HTTP {status}"
    if not parsed.entries:
        reason = parsed.get("bozo_exception") or "no stories in feed"
        return [], str(reason)[:120]

    stories = []
    for entry in parsed.entries:
        title = clean_text(entry.get("title"))
        link = entry.get("link", "")
        published = entry_time(entry)
        if not title or not link.startswith(("http://", "https://")) or not published:
            continue

        source = feed["name"]
        # Google News carries the real outlet in <source> and appends " - Outlet" to titles
        if entry.get("source", {}).get("title"):
            source = entry.source.title
            title = re.sub(r"\s+-\s+" + re.escape(source) + r"$", "", title)
        title = DESK_PREFIX_RE.sub("", title)

        summary = DESK_PREFIX_RE.sub("", clean_text(entry.get("summary")))
        if norm_title(summary).startswith(norm_title(title)[:40]):
            summary = ""  # feeds that just repeat the headline

        stories.append({
            "title": title,
            "link": link,
            "source": source,
            "published": published,
            "summary": shorten(summary),
            "also": [],
        })
    return stories, None


def is_duplicate(story, kept):
    key = norm_title(story["title"])
    for other in kept:
        if difflib.SequenceMatcher(None, key, other["_key"]).ratio() >= SIMILARITY:
            return other
    return None


def build_sections(config, now):
    cutoff = now - dt.timedelta(hours=config["settings"].get("hours_back", 24))
    seen = []  # every story kept so far, across all sections
    sections, failures = [], []
    total_feeds = 0

    for section in config["sections"]:
        candidates = []
        for feed in section["feeds"]:
            total_feeds += 1
            stories, error = fetch_feed(feed)
            if error:
                failures.append((section["name"], feed["name"], error))
                print(f"  ✗ {section['name']} / {feed['name']}: {error}", file=sys.stderr)
                continue
            fresh = [s for s in stories if s["published"] >= cutoff]
            print(f"  ✓ {section['name']} / {feed['name']}: {len(fresh)} recent of {len(stories)}")
            candidates.extend(fresh)

        candidates.sort(key=lambda s: s["published"], reverse=True)
        kept = []
        for story in candidates:
            match = is_duplicate(story, seen)
            if match:
                if story["source"] != match["source"] and story["source"] not in match["also"]:
                    match["also"].append(story["source"])
                continue
            story["_key"] = norm_title(story["title"])
            seen.append(story)
            if len(kept) < section.get("max_items", 15):
                kept.append(story)
        sections.append({"name": section["name"], "stories": kept})

    return sections, failures, total_feeds


def when(published, now):
    local = published.astimezone(MYT)
    clock = local.strftime("%I:%M %p").lstrip("0")
    if local.date() == now.astimezone(MYT).date():
        return clock
    return f"Yesterday {clock}"


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1b1d21;--muted:#62666d;--line:#e4e2dc;--accent:#0b5cad;--chip:#eceae4}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--card:#1b1e23;--ink:#e9e7e2;--muted:#9aa0a8;--line:#2a2e35;--accent:#7cb4f0;--chip:#252930}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:28px 16px 48px}
header h1{margin:0;font-size:1.7rem;letter-spacing:-.01em}
.date{margin:2px 0 0;font-weight:600}
.meta{margin:4px 0 0;color:var(--muted);font-size:.9rem}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 8px}
nav a{background:var(--chip);color:var(--ink);text-decoration:none;padding:5px 12px;border-radius:999px;font-size:.88rem}
section{margin-top:28px}
h2{font-size:1.05rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:6px;margin:0 0 4px}
ol{list-style:none;margin:0;padding:0}
li{padding:14px 0;border-bottom:1px solid var(--line)}
li a.t{color:var(--ink);text-decoration:none;font-weight:600;font-size:1.02rem}
li a.t:hover{color:var(--accent);text-decoration:underline}
.s{margin:4px 0 0;color:var(--muted);font-size:.93rem}
.src{margin:4px 0 0;font-size:.82rem;color:var(--muted)}
.src b{color:var(--accent);font-weight:600}
.empty{color:var(--muted);padding:12px 0}
footer{margin-top:36px;color:var(--muted);font-size:.85rem}
footer a,a.refresh{color:var(--accent)}
a.refresh{font-weight:600}
.archive li a{color:var(--accent);text-decoration:none;font-weight:600}
"""


def page(title, body):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body><main>
{body}
</main></body>
</html>
"""


def refresh_link(config):
    url = config["settings"].get("refresh_url", "")
    if not url.startswith("https://github.com/"):
        return ""
    return (f"<p class='meta'><a class='refresh' href='{html.escape(url)}' target='_blank' rel='noopener'>"
            "Refresh now</a> · tap <b>Run workflow</b>, then reload this page in about a minute</p>")


def render_html(config, sections, failures, total_feeds, now):
    e = html.escape
    local = now.astimezone(MYT)
    count = sum(len(s["stories"]) for s in sections)
    parts = [
        "<header>",
        f"<h1>{e(config['settings']['title'])}</h1>",
        f"<p class='date'>{local.strftime('%A, %-d %B %Y')}</p>",
        f"<p class='meta'>Updated {local.strftime('%-I:%M %p')} MYT · {count} stories · "
        f"{total_feeds - len(failures)} of {total_feeds} feeds responded</p>",
        refresh_link(config),
        "</header>",
        "<nav>" + "".join(f"<a href='#{slug(s['name'])}'>{e(s['name'])}</a>" for s in sections) + "</nav>",
    ]
    for section in sections:
        parts.append(f"<section id='{slug(section['name'])}'><h2>{e(section['name'])}</h2>")
        if not section["stories"]:
            parts.append("<p class='empty'>Nothing new in this section today.</p></section>")
            continue
        parts.append("<ol>")
        for s in section["stories"]:
            also = f" · also in {e(', '.join(s['also']))}" if s["also"] else ""
            summary = f"<p class='s'>{e(s['summary'])}</p>" if s["summary"] else ""
            parts.append(
                f"<li><a class='t' href='{e(s['link'])}' target='_blank' rel='noopener noreferrer'>"
                f"{e(s['title'])}</a>{summary}"
                f"<p class='src'><b>{e(s['source'])}</b> · {when(s['published'], now)}{also}</p></li>"
            )
        parts.append("</ol></section>")

    footer = ["<footer>", "<p><a href='archive.html'>Past briefs</a></p>"]
    if failures:
        skipped = "; ".join(f"{e(sec)} / {e(name)}" for sec, name, _ in failures)
        footer.append(f"<p>Skipped today (feed did not respond): {skipped}</p>")
    footer.append("</footer>")
    parts.extend(footer)
    return page(f"{config['settings']['title']} · {local.strftime('%-d %b %Y')}", "\n".join(parts))


def render_markdown(config, sections, failures, now):
    local = now.astimezone(MYT)
    lines = [f"# {config['settings']['title']}: {local.strftime('%A, %-d %B %Y')}", ""]
    for section in sections:
        lines += [f"## {section['name']}", ""]
        if not section["stories"]:
            lines += ["_Nothing new today._", ""]
            continue
        for s in section["stories"]:
            title = s["title"].replace("[", "(").replace("]", ")")
            also = f", also in {', '.join(s['also'])}" if s["also"] else ""
            lines.append(f"1. [{title}]({s['link']}) ({s['source']}, {when(s['published'], now)}{also})")
        lines.append("")
    if failures:
        lines.append("Skipped today: " + "; ".join(f"{sec} / {name}" for sec, name, _ in failures))
    return "\n".join(lines) + "\n"


def write_archive(config, keep_days, today):
    cutoff = today - dt.timedelta(days=keep_days)
    pages = []
    for path in DOCS.glob("????-??-??.html"):
        day = dt.date.fromisoformat(path.stem)
        if day < cutoff:
            path.unlink()
        else:
            pages.append(day)
    items = "".join(
        f"<li><a href='{d.isoformat()}.html'>{d.strftime('%A, %-d %B %Y')}</a></li>"
        for d in sorted(pages, reverse=True)
    )
    body = (
        f"<header><h1>{html.escape(config['settings']['title'])}</h1>"
        f"<p class='meta'>Past briefs · <a href='index.html'>Today</a></p></header>"
        f"<section class='archive'><ol>{items}</ol></section>"
    )
    (DOCS / "archive.html").write_text(page("Past briefs", body), encoding="utf-8")


def main():
    config = yaml.safe_load((ROOT / "feeds.yml").read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(MYT).date()
    print(f"Building brief for {today} (MYT)")

    sections, failures, total_feeds = build_sections(config, now)
    if len(failures) == total_feeds:
        print("Every feed failed. Not overwriting the site.", file=sys.stderr)
        return 1

    DOCS.mkdir(exist_ok=True)
    DIGESTS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").touch()

    html_page = render_html(config, sections, failures, total_feeds, now)
    (DOCS / "index.html").write_text(html_page, encoding="utf-8")
    (DOCS / f"{today.isoformat()}.html").write_text(html_page, encoding="utf-8")
    (DIGESTS / f"{today.isoformat()}.md").write_text(
        render_markdown(config, sections, failures, now), encoding="utf-8"
    )
    write_archive(config, config["settings"].get("keep_days", 90), today)

    count = sum(len(s["stories"]) for s in sections)
    print(f"Done: {count} stories, {len(failures)} feed(s) skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
