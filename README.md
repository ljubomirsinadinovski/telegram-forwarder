# Telegram Forwarder

Copies new messages from one Telegram group to another chat or channel.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Get `API_ID` and `API_HASH` at https://my.telegram.org (API development tools) and put them in `forwarder.py`.

## Usage

List your chats and their IDs (the first run logs you in):

```bash
python forwarder.py --list
```

Put the IDs into `SOURCE_ID` and `TARGET_ID` in `forwarder.py`, then start forwarding:

```bash
python forwarder.py
```

Stop with Ctrl+C. Don't share `forwarder.session`: anyone with it can use the account.
