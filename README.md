# Telegram Monitoring Feed

Turn a list of Telegram channels into a browsable feed of what's posting,
what's popular, and what's spreading — without opening the Telegram app
once.

## Why this exists

As a disinformation reporter, I'm constantly scanning social media for
viral claims. And yet, time and again, I default to X. I mean yes,
there's lots of disinformation on X. But that's not why. It's because X
presents a clean, readable, scrollable feed of posts. For Telegram, on
the other hand, if I want to read even 100 posts across 10 channels, that
involves opening each channel's feed, scrolling, entering a new channel's
name, scrolling, etc. It's not a useful way to monitor.

Instead, I wanted to be able to scroll a searchable, X-like feed of
Telegram posts and quickly see which posts are most popular and which
topics are trending.

This tool is especially nice because you don't even need a Telegram
account, let alone API access or developer credentials. If you give it
the channel names, the tool will scrape directly from that channel's
public webpage (`t.me/s/channelname`) and read what's posted there.
Everything is saved locally to your machine, which makes archival easier
and keeps your data secure.

But, crucially: this tool is only as effective as the channels you give
it to look at. So spend some time developing a good list of channels
you'd like to monitor — more tips on how to do that below.

Happy monitoring!

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
`.gitignore`) — it's your own research list.

## Finding channels to monitor

This tool is only as good as the list you give it — it doesn't discover
anything on its own, it just watches the channels you already know about.
For this tool to be helpful, you'll need to spend a couple hours
developing a good dataset. A few ways I actually build that list:

- **Follow the forwards.** Once you've found one relevant channel, check
  what it reposts from and who reposts it. Telegram shows the original
  source on any forwarded message, which is usually the fastest way to
  map out a whole network starting from a single channel.
- **Search Telegram itself.** Telegram's in-app search can surface
  channels by keyword or topic. Personally, I dislike Telegram search and
  find it hard to find channel names this way.
- **Look for existing research.** Depending on your beat, researchers,
  NGOs, or academic projects sometimes maintain curated, categorized
  channel lists (for extremism, disinformation, election monitoring, and
  so on, in a given country or language). Search for one relevant to your
  beat before building a list from scratch. You can also reach out to
  researchers and ask if they'd consider sharing a dataset! Researchers
  are nice, especially if you're on a similar beat.
- **Watch who officials and outlets link to.** Politicians, movement
  figures, and partisan outlets often plug their own or allied channels
  in posts, bios, or on other platforms.
- **Revisit the list periodically.** Channels go private, get deleted, or
  get replaced by a "backup channel" after a ban. `audit_channels.py`
  (see below) catches channels that have gone dead, but it won't find new
  ones for you — that part stays a human judgment call.

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

To look further back:

```bash
python scraper.py --hours 72     # last 3 days instead of 24 hours
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

To regenerate for a different window:

```bash
python feed.py --hours 48
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

## Customizing for your channels

Two files ship with generic English examples that you'll likely want to
adjust once you know what your own channels actually look like.

**`filters.py`** drops ads and "subscribe to our backup channel" spam
from the feeds. Open the file and you'll see `AD_PATTERNS` and
`PROMO_PATTERNS` — lists of phrases like `"subscribe now"` or `"buy
now"`. If your channels use different spam phrases, copy an existing
line, swap the phrase inside the quotes for one you actually see, and
leave the rest of the line as-is.

**`trends.py`** has its own `STOPWORDS` list — common filler words
("the," "and," "also") that get ignored so the Trending page surfaces
real topics instead of grammar. If your channels post in a language
other than English, this list won't catch that language's filler words,
and Trending will fill up with meaningless function words instead of
real topics. To fix it:

1. Open `trends.py` and find the line that starts `STOPWORDS = {` near
   the top of the file.
2. Replace the words between the curly braces `{ }` with your own
   language's common filler words — each one in quotes, separated by
   commas, same shape as what's already there.
3. The fastest way to get that list: ask an AI assistant like Claude or
   ChatGPT something like *"give me the 100 most common French filler
   words as a Python list of lowercase, quoted strings"* and paste the
   answer straight in. Searching "[your language] stopwords list" also
   turns up ready-made ones, though you may need to reformat them into
   that quotes-and-commas style yourself.
4. Save the file and run `python trends.py` again. If it's still mostly
   grammar instead of real topics, you're missing some common words —
   add them the same way.

If you're monitoring channels in a language you don't read yourself, you
don't need to translate anything by hand: Chrome's built-in translate
feature (right-click anywhere on the page → Translate to English) works
on these feed pages the same as it does on any other website.

## A note on scraping etiquette

The scraper visits many channels' pages at once (10 at a time, by
default), automatically. Doing that in moderation is completely normal;
doing it too aggressively (an enormous channel list, or running it
constantly) can start to look like the kind of automated traffic a
website tries to block, and Telegram could begin refusing your requests
if it decides you're hitting it too hard.

In practice: keep your channel list to what you actually need rather than
adding channels you might not use, and don't run the scraper more often
than your work actually requires — every few hours is usually plenty;
once a minute is not. If you start seeing a lot of `request error` or
`HTTP ...` warnings in the scraper's output where you didn't before, that's a sign
to slow down: open `scraper.py` and lower the `WORKERS` number near the
top of the file (10 by default) so fewer requests go out at once.

## Limitations

Being upfront about what this can't do:

- **Public channels only.** There's no public preview page for a private
  group or chat, so there's nothing to scrape.
- **Search is literal.** `trace.py` and the search boxes match exact
  text, not variant spellings, typos, or paraphrases.
- **View counts aren't a verified fact.** They're the only reach signal
  public scraping can get, and they can be inflated. Treat "Popular" as a
  starting point for your own judgment, not a finding in itself.
- **The Trending page needs tuning to your channel list size.** It only
  counts a term as trending if it shows up on several *different*
  channels, not just several posts — otherwise one copy-pasted post reads
  as a fake spike. What counts as "several" depends on how many channels
  you're watching; if Trending comes back empty, try
  `python trends.py --min-channels 2` and raise it from there.

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
