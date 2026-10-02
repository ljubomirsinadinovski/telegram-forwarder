# Telegram Forwarder

Copies new messages from one Telegram group to another chat or channel.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Get API_ID and API_HASH

Do this on your own account:

1. Go to https://my.telegram.org.
2. Enter your phone number in international format, e.g. `+389 7x xxx xxx`.
3. Enter the code Telegram sends you. It arrives in the Telegram app from the official "Telegram" account, not by SMS.
4. Click **API development tools** and fill in the form:
   - App title: anything, e.g. `forwarder`
   - Short name: 5–32 letters/numbers, e.g. `ljforwarder`
   - URL: leave empty
   - Platform: Desktop
   - Description: leave empty
5. Click **Create application**.
6. Copy **App api_id** (a number) into `API_ID` and **App api_hash** (32 characters) into `API_HASH` in `forwarder.py`.

If step 5 shows a plain "ERROR" (common): turn off VPN and ad blocker, try another browser or a private window, use letters only in the short name, or wait an hour and retry.

Each account gets one app and the credentials don't expire. Keep the api_hash private.

## Usage

List your chats and their IDs (the first run logs you in):

```bash
python forwarder.py --list
```

Put the IDs into `forwarder.py`: the chats to copy from go in `SOURCES`, the chat to copy to goes in `TARGET_ID`.

```python
SOURCES = [
    (-1001111111111, None),   # whole group
    (-1003333333333, 57),     # only topic 57 of this group
]
TARGET_ID = -1002222222222
```

If a group has topics, `--list` prints them under the group. Use `None` to copy the whole group.

Each copied message starts with the author's name in bold. Set `SHOW_AUTHOR = False` to turn it off.

Then start forwarding:

```bash
python forwarder.py
```

Stop with Ctrl+C. Don't share `forwarder.session`: anyone with it can use the account.
