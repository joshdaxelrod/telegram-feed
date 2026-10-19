# Use

[Overview](../README.md) · [Install](install.md) · **Use** · [Getting good results](getting-good-results.md)

Everything below has to be run from inside the project folder — the same
one you moved into during [Install](install.md#download) (the one containing `README.md`,
`scraper.py`, and so on). **Every time you open a new Terminal window,
you need to redo two things first, in this order, before any command
below will work:**

**1. Navigate back into the project folder**, using `cd` followed by its
path — the same one you used during Install. For example, if you used
the ZIP method:

```bash
cd ~/Downloads/telegram-feed-main
```

(Use whatever path is actually correct for you — wherever you unzipped
it, or wherever you ran `git clone` if you used git instead.)

**2. Activate the virtual environment from [Setup](install.md#setup).** If your prompt
doesn't already start with `(venv)`, run:

```bash
source venv/bin/activate
```

<details>
<summary>Using Windows instead?</summary>

For step 1, `cd` works the same way, just with a Windows-style path, e.g.
`cd %USERPROFILE%\Downloads\telegram-feed-main`. For step 2, activate
with `venv\Scripts\activate` (Command Prompt) or
`venv\Scripts\Activate.ps1` (PowerShell) instead. Every command below is
also written as `python3 ...` — use `python ...` (drop the `3`) for all
of them.

</details>

## 1. Scrape

```bash
python3 scraper.py
```

This visits every channel in `channels.csv` and saves their posts from
the last 24 hours into a local file, `data/messages.db`. You'll see a
line per channel (e.g. `guardian: 146 new messages`) as it goes — when
it prints `Done.`, it's finished.

To look further back:

```bash
python3 scraper.py --hours 72     # last 3 days instead of 24 hours
```

**The first time you set this up, scrape a full week instead of a day:**

```bash
python3 scraper.py --hours 168    # once, when you're starting out
```

Here's why: the Trending page (see step 2) works by comparing how often a term
comes up *right now* against how often it normally comes up over the
past 7 days. If your database only has a day of history in it, there's
no real "normal" to compare against, and Trending will show nonsense —
everything looks like an "infinite spike," including plain grammar,
because there's nothing behind it. One bigger scrape up front fixes
this for good. After that, your regular daily (or however often you
like) scrapes keep that history continuously topped up. If a real gap
ever does open up (you stop scraping for a while, then pick it back up),
just run the `--hours 168` backfill again.

## 2. Generate the feed

```bash
python3 feed.py
```

This reads what you've scraped, writes four web pages into a `data/`
folder, and opens one of them in your browser automatically. Use the tabs
at the top of the page to switch between Trending, Popular, Random, and
Spotlight — each one also has a search box, and hovering the "?" next to
the title explains what that page is showing.

To regenerate for a different window:

```bash
python3 feed.py --hours 48
```

## 3. Search everything you've ever scraped

```bash
python3 trace.py "some name or phrase"
```

This opens a page in your browser, in the same style as the feed pages,
listing every post that matches — oldest first, each labeled with how long
after the first post it appeared (`first`, `+2.5h`, …) — so you can see
exactly when and where something started spreading. Like the feed pages,
it has a filter box, and each card links to the original post.

The feed pages' filter boxes only search the posts on that page; this
searches everything in your database, looking back 7 days by default. To
go further back:

```bash
python3 trace.py "some name or phrase" --hours 720    # last 30 days
```

## 4. Clean up dead channels

```bash
python3 audit_channels.py
```

Flags channels in your list that haven't produced a single scraped
message — usually a wrong handle, or a channel that's gone private or
been deleted. To remove those flagged channels from `channels.csv`
automatically (it asks you to confirm first), run:

```bash
python3 audit_channels.py --prune
```

## Where your data lives

Everything gets written into a `data/` folder, which is left out of the
repository — it's your scraped data, not part of the tool itself.

- **`data/messages.db`** is the database every scraped post goes into.
  Running the scraper again doesn't overwrite or duplicate anything — it
  just adds newly-seen posts and quietly skips ones it's already saved,
  so this file only ever grows. Nothing here is cleaned up automatically;
  if it gets too big, you can delete it and start fresh, but there's no
  getting back history you didn't capture at the time — Telegram's
  preview pages only show recent posts.
- **The feed pages** (`data/popular.html`, `data/trending.html`, and so
  on, plus their matching `.csv` files) are different: each one is a
  snapshot of "right now." Running `feed.py` again completely overwrites
  whichever feed you regenerate. If you want to keep a particular page
  around for reference, copy the file elsewhere first.

---

**Next: [Getting good results →](getting-good-results.md)**
