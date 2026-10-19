# Install

[Overview](../README.md) · **Install** · [Use](usage.md) · [Getting good results](getting-good-results.md)

## Requirements

These instructions are written for macOS, since that's what I use. The
tool itself is plain Python and runs the same way on Windows or Linux —
each macOS step below has a matching Windows dropdown right after it, if
that's what you're on.

- **Terminal** — the app where you'll type commands. Open it via
  Applications → Utilities → Terminal, or press `⌘ Space`, type
  "Terminal," and press Return.

  Throughout these instructions, gray boxes like the one below hold commands.
  Copy the text, paste it into Terminal, and press Return to run it:

  ```bash
  echo "like this"
  ```

  <details>
  <summary>Using Windows instead?</summary>

  Press the Windows key, type **Command Prompt**, and press Enter — that's
  your equivalent of Terminal for every step below.

  </details>

- **Python 3.10 or newer.** Check what you have by typing this into
  Terminal and pressing Return:

  ```bash
  python3 --version
  ```

  If it says 3.10 or higher, you're set. If it's older or missing,
  download the installer from [python.org](https://www.python.org/downloads/)
  and run it like any other Mac app.

  <details>
  <summary>Using Windows instead?</summary>

  Check your version with `python --version` (no `3`) instead. If it's
  older than 3.10 or missing, download the installer from
  [python.org](https://www.python.org/downloads/) — **on the first
  install screen, check the box that says "Add python.exe to PATH,"**
  or the `python` command won't be found afterward.

  From here on, anywhere these instructions say a command starting with
  `python3`, use `python` (no `3`) instead — that's the only difference
  for the rest of Install and Use, beyond what's called out in its own
  dropdown below.

  </details>

## Download

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

   <details>
   <summary>Using Windows instead?</summary>

   Unzip by right-clicking the downloaded file and choosing **Extract
   All**, then move into the folder with:

   ```bat
   cd %USERPROFILE%\Downloads\telegram-feed-main
   ```

   (or `cd %USERPROFILE%\Desktop\telegram-feed-main` if you moved it to
   the Desktop first, etc.)

   </details>

**If you use git instead:**

```bash
git clone https://github.com/joshdaxelrod/telegram-feed.git
cd telegram-feed
```

(Identical on every OS.)

**From here, both paths continue the same way.**

## Setup

First, create a private, self-contained copy of Python just for this tool
(called a "virtual environment"). This avoids two common problems: newer
Macs often refuse to let you install packages directly ("externally
managed environment" errors), and if your computer has more than one
copy of Python installed, it keeps this tool from accidentally using the
wrong one.

```bash
python3 -m venv venv
source venv/bin/activate
```

<details>
<summary>Using Windows instead?</summary>

**Command Prompt:**
```bat
python -m venv venv
venv\Scripts\activate
```

**PowerShell:** same, but activate with `venv\Scripts\Activate.ps1`
instead. If PowerShell refuses to run it with an "execution policies"
error, run this once, then try activating again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

</details>

You'll know it worked because your prompt now starts with `(venv)`. Do
this once per terminal session — any time you close the terminal and come
back later to use the tool, run the activate command again first (from
inside the project folder) before running any of the commands in
[Use](usage.md).

Now install the two small libraries this tool depends on:

```bash
python3 -m pip install -r requirements.txt
```

<details>
<summary>Using Windows instead?</summary>

```bat
python -m pip install -r requirements.txt
```

</details>

`pip` is Python's package installer — this downloads two small helper
libraries (`requests`, for fetching web pages, and `beautifulsoup4`, for
reading what's on them) onto your computer. If you see text scroll by
ending in something like "Successfully installed," it worked.

Next, create your own list of channels to monitor. A template is
included:

```bash
cp channels.example.csv channels.csv
```

<details>
<summary>Using Windows instead?</summary>

```bat
copy channels.example.csv channels.csv
```

</details>

Open `channels.csv` in any spreadsheet app (Numbers, Excel, Google
Sheets) or a plain text editor, and replace the example rows with your
own channels — one handle per line (for tips on choosing them, see
[Finding channels to monitor](getting-good-results.md#finding-channels-to-monitor)):

```csv
handle
somechannel
otherchannel
```

A channel's **handle** is the part of its Telegram link after `t.me/` —
if a channel's link is `t.me/somechannel`, its handle is `somechannel`.

`channels.csv` is set up to stay only on your computer — it never gets
uploaded anywhere, including to GitHub, even if you download updates to
the tool later. That's on purpose: it's your own research list.

**That's it — you're installed.** Everything from here ([Use](usage.md)) is
just running the tool, not setting it up again.

---

**Next: [Use →](usage.md)**
