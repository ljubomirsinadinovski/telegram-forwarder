import sys
import asyncio
import logging
import tempfile
from telethon import TelegramClient, events
from telethon.errors import ChatForwardsRestrictedError

# ---- fill these in ----
API_ID = 1234567                 # from my.telegram.org (friend's account)
API_HASH = "your_api_hash"
SOURCE_ID = -1001111111111       # private group (get it with --list)
TARGET_ID = -1002222222222       # your mutual channel (get it with --list)
# -----------------------

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
log = logging.getLogger("forwarder")


async def main():
    client = TelegramClient(
        "forwarder", API_ID, API_HASH,
        connection_retries=None,   # keep reconnecting forever (e.g. after laptop sleep)
        retry_delay=5,
    )
    await client.start()           # first run asks for phone, code and 2FA password

    if "--list" in sys.argv:
        async for d in client.iter_dialogs():
            print(d.id, " ", d.name)
        await client.disconnect()
        return

    await client.get_dialogs()     # make sure both chats are known

    async def repost_fast(messages):
        """Reuse the media already on Telegram's servers (no download)."""
        if len(messages) == 1:
            await client.send_message(TARGET_ID, messages[0])   # copy, no "Forwarded from"
        else:
            await client.send_file(
                TARGET_ID,
                [m.media for m in messages],
                caption=[m.message or "" for m in messages],
                parse_mode=None,   # captions are plain text; don't let markdown eat underscores
            )

    async def repost_reupload(messages):
        """Source group restricts saving content: download the media and upload it again."""
        with tempfile.TemporaryDirectory() as tmp:
            paths = [await m.download_media(file=tmp) for m in messages]
            if len(messages) == 1:
                m, path = messages[0], paths[0]
                if path:
                    await client.send_file(TARGET_ID, path, caption=m.message,
                                           formatting_entities=m.entities,
                                           supports_streaming=True)
                else:
                    await client.send_message(TARGET_ID, m.message,
                                              formatting_entities=m.entities)
            else:
                await client.send_file(
                    TARGET_ID,
                    paths,
                    caption=[m.message or "" for m in messages],
                    parse_mode=None,
                    supports_streaming=True,
                )

    async def repost(messages):
        messages = [m for m in messages if not m.action]   # skip joins, pins, etc.
        if not messages:
            return
        try:
            await repost_fast(messages)
        except ChatForwardsRestrictedError:
            await repost_reupload(messages)

    @client.on(events.NewMessage(chats=SOURCE_ID))
    async def on_message(event):
        if event.message.grouped_id:
            return   # album, handled below
        try:
            await repost([event.message])
            log.info("copied message %s", event.message.id)
        except Exception:
            log.exception("failed to copy %s", event.message.id)

    @client.on(events.Album(chats=SOURCE_ID))
    async def on_album(event):
        try:
            await repost(event.messages)
            log.info("copied album of %d", len(event.messages))
        except Exception:
            log.exception("failed to copy album")

    log.info("listening on %s -> %s (Ctrl+C to stop)", SOURCE_ID, TARGET_ID)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
