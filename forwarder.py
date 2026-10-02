import sys
import asyncio
import logging
import tempfile
from telethon import TelegramClient, events, functions
from telethon.errors import ChatForwardsRestrictedError

# ---- fill these in ----
API_ID = 1234567                 # from my.telegram.org (friend's account)
API_HASH = "your_api_hash"
# (chat id, topic id) pairs to copy from, both from --list.
# Topic None = the whole chat. The same chat can be listed with several topics.
SOURCES = [
    (-1001111111111, None),
    (-1003333333333, 57),
]
TARGET_ID = -1002222222222       # where everything is copied to (get it with --list)
# -----------------------

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
log = logging.getLogger("forwarder")


def topic_of(message):
    """Topic id of a message in a forum group (1 = General)."""
    r = message.reply_to
    if not r or not r.forum_topic:
        return 1
    return r.reply_to_top_id or r.reply_to_msg_id


SOURCE_CHATS = list({chat for chat, _ in SOURCES})


def wanted(message):
    return any(
        message.chat_id == chat and (topic is None or topic_of(message) == topic)
        for chat, topic in SOURCES
    )


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
            if getattr(d.entity, "forum", False):
                topics = await client(functions.messages.GetForumTopicsRequest(
                    peer=d.entity, offset_date=None, offset_id=0, offset_topic=0, limit=100))
                for t in topics.topics:
                    print("    topic", t.id, " ", getattr(t, "title", "(deleted)"))
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

    @client.on(events.NewMessage(chats=SOURCE_CHATS))
    async def on_message(event):
        if event.message.grouped_id or not wanted(event.message):
            return   # albums are handled below
        try:
            await repost([event.message])
            log.info("copied message %s from %s", event.message.id, event.chat_id)
        except Exception:
            log.exception("failed to copy %s from %s", event.message.id, event.chat_id)

    @client.on(events.Album(chats=SOURCE_CHATS))
    async def on_album(event):
        if not wanted(event.messages[0]):
            return
        try:
            await repost(event.messages)
            log.info("copied album of %d from %s", len(event.messages), event.chat_id)
        except Exception:
            log.exception("failed to copy album")

    log.info("listening on %s -> %s (Ctrl+C to stop)", SOURCES, TARGET_ID)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
