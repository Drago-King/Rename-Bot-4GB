# Channel & Group Auto-Rename Plugin
# - Original caption preserved
# - Thumbnail swapped with owner's saved thumb
# - Format: document or video (per channel)
# - Template rename (optional)
# - Queue: one file at a time, safe for bulk posts

import os
import time
import asyncio
import pymongo
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image
from config import DATABASE_URL, DATABASE_NAME
from helper.ffmpeg import add_metadata

# ─── MongoDB ──────────────────────────────────────────────────────────────────
mongo = pymongo.MongoClient(DATABASE_URL)
db = mongo[DATABASE_NAME]
ch_col = db["channel_settings"]
users_col = db["user"]

# ─── Queue ────────────────────────────────────────────────────────────────────
_queue = asyncio.Queue()

async def _queue_worker():
    while True:
        fn, args, kwargs = await _queue.get()
        try:
            await fn(*args, **kwargs)
        except Exception as e:
            print(f"[RenameQueue Error] {e}")
        finally:
            _queue.task_done()
        await asyncio.sleep(0.5)

# ─── DB Helpers ───────────────────────────────────────────────────────────────

def get_channel_settings(channel_id: int) -> dict:
    doc = ch_col.find_one({"_id": channel_id})
    if not doc:
        doc = {
            "_id": channel_id,
            "enabled": False,
            "owner_id": None,
            "format": "document",
            "template": None,
        }
        ch_col.insert_one(doc)
    return doc

def save_channel_settings(channel_id: int, data: dict):
    ch_col.update_one({"_id": channel_id}, {"$set": data}, upsert=True)

def get_user_data(user_id: int) -> dict:
    return users_col.find_one({"_id": user_id}) or {}

def apply_template(template: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    return (
        template
        .replace("{filename}", base)
        .replace("{ext}", ext.lstrip("."))
    )

# ─── Commands ─────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("addchannel"))
async def add_channel(client: Client, message: Message):
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "❌ Usage: /addchannel <@username or chat_id>\n\n"
            "Works for channels and groups.\n"
            "Example: /addchannel @MyChannel\n\n"
            "Bot must be admin with Post & Delete permissions."
        )
    target = args[1]
    try:
        chat = await client.get_chat(target)
        channel_id = chat.id
    except Exception as e:
        return await message.reply_text(f"❌ Could not find: {e}")

    try:
        me = await client.get_me()
        bot_member = await client.get_chat_member(channel_id, me.id)
        if not bot_member.privileges:
            return await message.reply_text("❌ Bot is not an admin there.")
    except Exception as e:
        return await message.reply_text(f"❌ Admin check failed: {e}")

    save_channel_settings(channel_id, {
        "enabled": True,
        "owner_id": message.from_user.id,
        "channel_title": chat.title,
    })

    s = get_channel_settings(channel_id)
    fmt = s.get("format", "document")
    tmpl = s.get("template") or "Keep original filename"

    await message.reply_text(
        f"✅ Linked: {chat.title}\n\n"
        f"📁 Format: {fmt}\n"
        f"📝 Template: {tmpl}\n"
        f"🖼 Thumbnail: your saved thumbnail\n"
        f"💬 Caption: original (unchanged)\n\n"
        f"Set format: /chformat {target} document|video\n"
        f"Set template: /chtemplate {target} {{filename}}.{{ext}}\n\n"
        f"Every file posted will be auto-renamed! 🚀"
    )


@Client.on_message(filters.private & filters.command("removechannel"))
async def remove_channel(client: Client, message: Message):
    args = message.command
    if len(args) < 2:
        return await message.reply_text("❌ Usage: /removechannel <@username or id>")
    try:
        chat = await client.get_chat(args[1])
    except Exception as e:
        return await message.reply_text(f"❌ Not found: {e}")
    save_channel_settings(chat.id, {"enabled": False})
    await message.reply_text(f"✅ Auto-rename disabled for: {chat.title}")


@Client.on_message(filters.private & filters.command("chformat"))
async def set_ch_format(client: Client, message: Message):
    args = message.command
    if len(args) < 3:
        return await message.reply_text(
            "❌ Usage: /chformat <@channel> <document|video>\n"
            "Example: /chformat @MyChannel video"
        )
    fmt = args[2].lower()
    if fmt not in ("document", "video"):
        return await message.reply_text("❌ Must be 'document' or 'video'")
    try:
        chat = await client.get_chat(args[1])
    except Exception as e:
        return await message.reply_text(f"❌ Not found: {e}")
    s = get_channel_settings(chat.id)
    if s.get("owner_id") != message.from_user.id:
        return await message.reply_text("❌ You didn't link this channel.")
    save_channel_settings(chat.id, {"format": fmt})
    await message.reply_text(f"✅ Format set to: {fmt}")


@Client.on_message(filters.private & filters.command("chtemplate"))
async def set_ch_template(client: Client, message: Message):
    args = message.text.split(None, 2)
    if len(args) < 3:
        return await message.reply_text(
            "❌ Usage: /chtemplate <@channel> <template>\n\n"
            "Placeholders: {filename} {ext}\n"
            "Example: /chtemplate @MyChannel {filename} [EchoFlix].{ext}\n"
            "Send 'off' to keep original filename."
        )
    try:
        chat = await client.get_chat(args[1])
    except Exception as e:
        return await message.reply_text(f"❌ Not found: {e}")
    s = get_channel_settings(chat.id)
    if s.get("owner_id") != message.from_user.id:
        return await message.reply_text("❌ You didn't link this channel.")
    val = None if args[2].strip().lower() == "off" else args[2].strip()
    save_channel_settings(chat.id, {"template": val})
    await message.reply_text(
        f"✅ Template {'disabled' if not val else 'saved'}!"
        + (f"\n📝 {val}" if val else "")
    )


@Client.on_message(filters.private & filters.command("mychannels"))
async def my_channels(client: Client, message: Message):
    uid = message.from_user.id
    channels = list(ch_col.find({"owner_id": uid, "enabled": True}))
    if not channels:
        return await message.reply_text("No channels linked.\nUse /addchannel to add one.")
    text = f"📡 Linked chats ({len(channels)}):\n\n"
    for ch in channels:
        title = ch.get("channel_title", str(ch["_id"]))
        fmt = ch.get("format", "document")
        tmpl = ch.get("template") or "original name"
        text += f"• {title}\n  Format: {fmt} | Template: {tmpl}\n\n"
    await message.reply_text(text)


# ─── Core Rename Logic ────────────────────────────────────────────────────────

async def _do_rename(client: Client, message: Message):
    channel_id = message.chat.id
    s = get_channel_settings(channel_id)

    if not s.get("enabled"):
        return

    # Detect file
    file = None
    orig_name = None

    if message.document:
        file = message.document
        orig_name = file.file_name or f"file_{file.file_unique_id}"
    elif message.video:
        file = message.video
        orig_name = file.file_name or f"video_{file.file_unique_id}.mp4"
    elif message.audio:
        file = message.audio
        orig_name = file.file_name or f"audio_{file.file_unique_id}.mp3"
    else:
        return

    original_caption = message.caption or None
    template = s.get("template")
    new_name = apply_template(template, orig_name) if template else orig_name

    fmt = s.get("format", "document")
    send_as_video = (fmt == "video")

    owner_id = s.get("owner_id")
    thumb_file_id = None
    use_metadata = False
    metadata_code = None
    ph_path = None

    if owner_id:
        user_data = get_user_data(owner_id)
        thumb_file_id = user_data.get("file_id")
        use_metadata = user_data.get("metadata", False)
        metadata_code = user_data.get("metadata_code")

    # Download
    os.makedirs("downloads", exist_ok=True)
    safe_name = new_name.replace("/", "_").replace("\0", "_")
    file_path = f"downloads/{int(time.time())}_{safe_name}"

    try:
        path = await client.download_media(message=file, file_name=file_path)
    except Exception as e:
        print(f"[Download Error] {e}")
        return

    # Metadata
    final_path = path
    if use_metadata and metadata_code:
        os.makedirs("Metadata", exist_ok=True)
        metadata_path = f"Metadata/{int(time.time())}_{safe_name}"
        try:
            await add_metadata(path, metadata_path, metadata_code, message)
            final_path = metadata_path
        except Exception:
            final_path = path

    # Thumbnail
    if thumb_file_id:
        try:
            ph_path = await client.download_media(thumb_file_id)
            img = Image.open(ph_path).convert("RGB")
            img = img.resize((320, 320))
            img.save(ph_path, "JPEG")
        except Exception:
            ph_path = None

    # Upload
    try:
        if send_as_video:
            await client.send_video(
                chat_id=channel_id,
                video=final_path,
                file_name=new_name,
                thumb=ph_path,
                supports_streaming=True,
                caption=original_caption,
            )
        else:
            await client.send_document(
                chat_id=channel_id,
                document=final_path,
                file_name=new_name,
                thumb=ph_path,
                caption=original_caption,
            )

        await asyncio.sleep(1)
        try:
            await client.delete_messages(channel_id, message.id)
        except Exception:
            pass

    except Exception as e:
        print(f"[Upload Error] {e}")

    finally:
        for p in [final_path, ph_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


# ─── Handler ──────────────────────────────────────────────────────────────────

@Client.on_message(
    filters.channel |
    (filters.group & (filters.document | filters.video | filters.audio))
)
async def channel_auto_rename(client: Client, message: Message):
    s = get_channel_settings(message.chat.id)
    if not s.get("enabled"):
        return
    if not (message.document or message.video or message.audio):
        return
    await _queue.put((_do_rename, (client, message), {}))


