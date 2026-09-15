# Telegram Monitoring Feed

Turn a list of Telegram channels into a browsable feed of what's posting,
what's popular, and what's spreading — without opening the Telegram app
once.

## Why this exists

A lot of my reporting on extremism and disinformation involves keeping an
eye on Telegram channels. But Telegram's own app doesn't give you any way
to see what's viral across a whole set of channels at once, what's
trending across a scene, or search everything you've seen over the last
week. So I built this: point it at a list of public channel handles, and
it scrapes what they've posted into a database, then generates a set of
readable web pages — like a private, editorial version of a social feed,
built from exactly the channels you care about.

No Telegram account, API key, or developer credentials of any kind are
required. It works by visiting each channel's public preview page (the
same page you'd see if you pasted a `t.me/s/channelname` link into a
browser without being logged in) and reading what's posted there.

## Screenshots

*(Demo data below is from a handful of mainstream news channels — not a
real research target list.)*

**Trending** — a narrative taking off across multiple channels, before it's an obviously "popular" post:

<img src="screenshots/trending.png" width="600" alt="Trending feed">

**Popular** — the most-viewed posts right now:

<img src="screenshots/popular.png" width="600" alt="Popular feed">

**Random** — a random sample for browsing outside the rankings:

<img src="screenshots/random.png" width="600" alt="Random feed">

**Spotlight** — each channel's own top post, so small channels aren't buried:

<img src="screenshots/spotlight.png" width="600" alt="Spotlight feed">

## What it does, in plain terms

- **Scrape** — visits every channel in your list and saves what they've
  posted recently into a small local database on your own computer.
  Nothing is uploaded anywhere.
- **Feed** — turns what's scraped into four browsable web pages:
  - **Trending** — words or phrases spreading across several channels
    right now, more than they normally do. This is the one most likely to
    catch something before it's an obviously "popular" post.
  - **Popular** — the most-viewed posts right now. If the same post got
    copy-pasted across five channels, it's shown once with a badge saying
    so, instead of cluttering the page five times.
  - **Random** — a random sample, so you're not only ever seeing whatever
    the popularity ranking surfaces.
  - **Spotlight** — each channel's own best post, so a quiet channel's
    one interesting post of the day shows up next to a busy channel's
    best post, instead of getting buried underneath it.
- **Search** — full-text search across everything you've ever scraped, by
  keyword and date range, showing chronologically how something spread.
- **Audit** — flags channels in your list that never produced a single
  post, usually a sign the handle is wrong or the channel's gone private.

## Requirements

These instructions are written for macOS, since that's what I use. The
tool itself is plain Python and should run on Windows or Linux too, but
you may need to adapt the setup steps below.

- **Terminal** — the app where you'll type commands. Open it via
  Applications → Utilities → Terminal, or press `⌘ Space`, type
  "Terminal," and press Return.

  Throughout this README, gray boxes like the one below hold commands.
  Copy the text, paste it into Terminal, and press Return to run it:

  ```bash
  echo "like this"
  ```

- **Python 3.10 or newer.** Check what you have by typing this into
  Terminal and pressing Return:

  ```bash
  python3 --version
  ```

  If it says 3.10 or higher, you're set. If it's older or missing,
  download the installer from [python.org](https://www.python.org/downloads/)
  and run it like any other Mac app.

## Install

**If you don't use git (the easiest path for most people):**

1. Click the green **Code** button near the top of this page, then
   **Download ZIP**.
2. Find the downloaded file — usually in your **Downloads** folder — and
   double-click it to unzip. This creates a folder called
   `telegram-feed-main`.
3. In Terminal, move into that folder:

   ```bash
   cd ~/Downloads/telegram-feed-main
   ```

   (If you moved the folder somewhere else first, like the Desktop, use
   that path instead — e.g. `cd ~/Desktop/telegram-feed-main`.)

**If you use git instead:**

```bash
git clone https://github.com/joshdaxelrod/telegram-feed.git
cd telegram-feed
```

**From here, both paths continue the same way.**

## Setup

Install the two small libraries this tool depends on:

```bash
pip install -r requirements.txt
```

`pip` is Python's package installer — this downloads two small helper
libraries (`requests`, for fetching web pages, and `beautifulsoup4`, for
reading what's on them) onto your computer. If you see text scroll by
ending in something like "Successfully installed," it worked.

Next, create your own list of channels to monitor. A template is
included:

```bash
cp channels.example.csv channels.csv
```

Open `channels.csv` in any spreadsheet app (Numbers, Excel, Google
Sheets) or a plain text editor, and replace the example rows with your
own channels — one handle per line:

```csv
handle
somechannel
otherchannel
```

A channel's **handle** is the part of its Telegram link after `t.me/` —
if a channel's link is `t.me/somechannel`, its handle is `somechannel`.

`channels.csv` is left out of this repository on purpose (see
`.gitignore`) — it's your own research list, and deciding what to
monitor is an editorial call, not something this tool should assume or
publish for you.

**Optional — grouping channels.** If you want to filter by group later
(e.g. checking only your highest-priority channels, or only the ones in a
given language), add a second column called `tier` and put any label you
want in it:

```csv
handle,tier
somechannel,core
otherchannel,watch
```

The label can be anything — it has no built-in meaning, it's just there
so you can filter with `--tier core` later on. If you don't need this,
skip it; every command below works fine with just a handle column.

## Usage

Everything below is run from Terminal, from inside the project folder
(the one you `cd`'d into during Install).

### 1. Scrape

```bash
python scraper.py
```

This visits every channel in `channels.csv` and saves their posts from
the last 24 hours into a local file, `data/messages.db`. You'll see a
line per channel (e.g. `tagesschau: 146 new messages`) as it goes — when
it prints `Done.`, it's finished.

To look further back, or scrape only one tier:

```bash
python scraper.py --hours 72     # last 3 days instead of 24 hours
python scraper.py --tier core    # only channels tagged "core"
```

### 2. Generate the feed

```bash
python feed.py
```

This reads what you've scraped, writes four web pages into a `data/`
folder, and opens one of them in your browser automatically. Use the tabs
at the top of the page to switch between Trending, Popular, Random, and
Spotlight — each one also has a search box, and hovering the "?" next to
the title explains what that page is showing.

To regenerate for a different window or tier:

```bash
python feed.py --hours 48 --tier core
```

### 3. Search everything you've ever scraped

```bash
python trace.py "some name or phrase"
```

Unlike the feed pages, which only show whatever window you generated them
for, this searches the *entire* database and prints every match in
chronological order — useful for seeing exactly when and where something
started spreading.

### 4. Clean up dead channels

```bash
python audit_channels.py
```

Flags channels in your list that haven't produced a single scraped
message — usually a wrong handle, or a channel that's gone private or
been deleted. Add `--prune` to remove them from `channels.csv`
automatically (it asks you to confirm first).

Feeds and the database are written to `data/`, which is also left out of
the repository — it's your scraped data, not part of the tool itself.

## Customizing for your channels

`filters.py` holds a short list of patterns used to drop ads and
"subscribe to our backup channel" spam from the feeds. They're written
for a German-language Telegram scene, since that's what I monitor — open
the file and edit `AD_PATTERNS` / `PROMO_PATTERNS` if you're watching
channels in another language.

`trends.py` also has its own `STOPWORDS` list (common filler words like
"the," "and," "also") tuned for German, for the same reason. If your
channels post in a different language, that list will need editing too,
or the Trending page will surface a lot of meaningless function words
instead of real topics.

## A note on scraping etiquette

The scraper hits `t.me/s/<channel>` with a pool of 10 workers running at
once, across every channel in your list. Be a considerate scraper: keep
your channel list to what you actually need, don't run it more often than
your work requires, and back off (lower `WORKERS` in `scraper.py`, or
scrape a smaller `--tier` at a time) if you notice requests failing.

## Limitations

Being upfront about what this can't do:

- **Public channels only.** There's no public preview page for a private
  group or chat, so there's nothing to scrape.
- **Telegram only.** No Twitter/X, Bluesky, Facebook, or anything else.
- **Search is literal.** `trace.py` and the search boxes match exact
  text, not variant spellings, typos, or paraphrases.
- **View counts aren't a verified fact.** They're the only reach signal
  public scraping can get, and they can be inflated. Treat "Popular" as a
  starting point for your own judgment, not a finding in itself.
- **No translation built in.** If you're monitoring channels in a
  language you don't read, your browser's own translate feature (e.g.
  right-click → Translate in Chrome) works on these pages like any other
  webpage.
- **The Trending page needs tuning to your channel list size.** It only
  counts a term as trending if it shows up on several *different*
  channels, not just several posts — otherwise one copy-pasted post reads
  as a fake spike. What counts as "several" depends on how many channels
  you're watching; if Trending comes back empty, try
  `python trends.py --min-channels 2` and raise it from there.
- **It depends on Telegram's page staying the same.** The scraper reads a
  specific page layout. If Telegram changes it, scraping will start
  failing until `scraper.py` is updated to match — not complicated, just
  inherently fragile.

## Tests

```bash
python -m pytest
```

## License

MIT — see [LICENSE](LICENSE).

Built with AI assistance (Claude), reviewed and tested by me.

## About

Written by [Josh Axelrod](https://josh-axelrod.com), an investigative
reporter and 2023–24 Fulbright Journalism Fellow based in Berlin,
Germany. He covers extremism, disinformation, and technology; his work
has appeared in WIRED, Mother Jones, Deutsche Welle, Die Zeit, The Daily
Beast, NPR, and more.
