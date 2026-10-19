# Getting good results

[Overview](../README.md) · [Install](install.md) · [Use](usage.md) · **Getting good results**

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
  (see [Use](usage.md#4-clean-up-dead-channels)) catches channels that have gone dead, but it won't find new
  ones for you — that part stays a human judgment call.

## Customizing for your channels

You'll likely want to adjust two things once you know what your own
channels actually look like. Both work the same way: add a plain text
file with your own words or phrases in it, one per line, and it gets
picked up automatically.

On a Mac, if you make the file in TextEdit, choose **Format → Make Plain
Text** before saving — otherwise TextEdit saves it in a different format
the tool can't read.

**Filtering out ads and spam — `filters.local.txt`.** `filters.py`
drops ads and "subscribe to our backup channel" spam from the feeds
using a built-in list of English example phrases (things like
`"subscribe now"` or `"buy now"`). If your channels use different spam
phrases — in English or any other language — create a file called
`filters.local.txt` in the project folder (`telegram-feed-main`, the one
with `scraper.py` in it), and put one spam phrase per line:

```
jetzt abonnieren
folgt uns auf
```

Any post containing one of those phrases gets filtered out, in addition
to the built-in examples. Lines starting with `#` are ignored, so you
can leave yourself notes. An AI assistant can help you build this list:
paste in a handful of real ad/promo posts from your own channels and ask
something like *"what phrases in here are advertising or 'subscribe to
our channel' spam? List each one on its own line, exactly as it
appears"* — it's often faster at spotting the pattern across examples
than doing it by eye.

**Filtering out grammar so Trending shows real topics —
`stopwords.local.txt`.** `trends.py` uses a similar built-in list of
common English filler words ("the," "and," "also") — words that are so
common they get ignored, so the Trending page surfaces actual topics
instead of grammar. If your channels post in a language other than
English, this list won't catch that language's filler words, and
Trending will fill up with meaningless function words instead of real
topics. Fix it the same way: create a file called `stopwords.local.txt`
in the project folder, one filler word per line:

```
der
die
und
```

The fastest way to fill this in: ask an AI assistant like Claude or
ChatGPT something like *"give me the 300 most common French filler
words — articles, pronouns, conjunctions, prepositions, and every common
form of 'to be' and 'to have' — one per line, all lowercase"* and paste
the answer straight into the file. Aim high rather than low: a real
stopword list needs a few hundred words to actually work (off-the-shelf
English/German lists from libraries like NLTK run 200–600+ words), and
it's much faster to trim a list that's too aggressive than to keep
finding one leaked word at a time.

Either way, save the file and run the tool again — `python3 trends.py`
or `python3 feed.py` for stopwords, `python3 feed.py` for filters. If
Trending is still mostly grammar instead of real topics, you're missing
some common words; add them the same way.

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
  `python3 feed.py --min-channels 2` and raise it from there.
- **Trending doesn't work on non-Latin scripts.** It splits text into
  words using a pattern that only matches Latin letters (English,
  German, French, and similar). Channels posting in Arabic, Russian,
  Chinese, or another non-Latin script won't register any words, so
  Trending will always come back empty for them — Popular, Random, and
  Spotlight are unaffected, since they don't need to split text into
  words at all.
