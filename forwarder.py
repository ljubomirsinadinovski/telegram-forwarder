import sys
import asyncio
import logging
import tempfile
import copy
from telethon import TelegramClient, events, functions, utils
from telethon.errors import ChatForwardsRestrictedError
from telethon.tl.types import MessageEntityBold, MessageMediaWebPage

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
SHOW_AUTHOR = True               # put the sender's name in bold above each message
# -----------------------

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
log = logging.getLogger("forwarder")


def topic_of(message):
    """Topic id of a message in a forum group (1 = General)."""
    r = message.reply_to
    if not r or not r.forum_topic:
        return 1
    return r.reply_to_top_id or r.reply_to_msg_id


async def author_of(message):
    if message.post_author:          # signed channel post
        return message.post_author
    sender = await message.get_sender()
    return utils.get_display_name(sender) if sender else None


def with_header(text, entities, header):
    """Put a bold header line above the text, shifting existing formatting down."""
    text, entities = text or "", list(entities or [])
    if not header:
        return text, entities
    prefix = header + "\n" if text else header
    shift = len(prefix.encode("utf-16-le")) // 2   # Telegram offsets count UTF-16 units
    bold_len = len(header.encode("utf-16-le")) // 2
    moved = []
    for e in entities:
        e = copy.copy(e)
        e.offset += shift
        moved.append(e)
    return prefix + text, [MessageEntityBold(0, bold_len)] + moved


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

    async def captions(messages):
        """Text and formatting for each message, with the author on the captioned one."""
        header = await author_of(messages[0]) if SHOW_AUTHOR else None
        first = next((i for i, m in enumerate(messages) if m.message), 0)
        return [
            with_header(m.message, m.entities, header if i == first else None)
            for i, m in enumerate(messages)
        ]

    async def send(messages, files):
        texts = await captions(messages)
        if len(messages) == 1:
            (text, entities), = texts
            await client.send_message(TARGET_ID, text, formatting_entities=entities,
                                      file=files[0], parse_mode=None,
                                      link_preview=isinstance(messages[0].media, MessageMediaWebPage),
                                      supports_streaming=True)
        else:
            await client.send_file(TARGET_ID, files,
                                   caption=[t for t, _ in texts],
                                   formatting_entities=[e for _, e in texts],
                                   parse_mode=None, supports_streaming=True)

    def media_of(m):
        return None if isinstance(m.media, MessageMediaWebPage) else m.media

    async def repost(messages):
        messages = [m for m in messages if not m.action]   # skip joins, pins, etc.
        if not messages:
            return
        try:
            # reuse the media already on Telegram's servers (no download)
            await send(messages, [media_of(m) for m in messages])
        except ChatForwardsRestrictedError:
            # source restricts saving content: download the media and upload it again
            with tempfile.TemporaryDirectory() as tmp:
                paths = [await m.download_media(file=tmp) if media_of(m) else None
                         for m in messages]
                await send(messages, paths)

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
