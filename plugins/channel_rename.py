# Channel Auto-Rename Plugin
# Auto-renames files in channel using original caption + saved thumbnail
# Format (document/video) configurable per channel via /chformat

import os
import time
import asyncio
import pymongo
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image
from config import DATABASE_URL, DATABASE_NAME, LOG_CHANNEL, API_ID, API_HASH, STRING_SESSION
from helper.progress import progress_for_pyrogram
from helper.ffmpeg import add_metadata

# ─── MongoDB ──────────────────────────────────────────────────────────────────
mongo = pymongo.MongoClient(DATABASE_URL)
db = mongo[DATABASE_NAME]
ch_col = db["channel_settings"]
users_col = db["user"]

# ─── Helpers ──────────────────────────────────────────────────────────────────

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
    """Usage: /addchannel <@username or channel_id>"""
    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "❌ Usage: /addchannel <@username or chat_id>\n\n"
            "Works for both channels and groups.\n"
            "Example: /addchannel @MyChannel\n\n"
            "Make sure bot is admin with Post & Delete permissions."
        )

    target = args[1]
    try:
        chat = await client.get_chat(target)
        channel_id = chat.id
    except Exception as e:
        return await message.reply_text(f"❌ Could not find channel: {e}")

    try:
        bot_member = await client.get_chat_member(channel_id, (await client.get_me()).id)
        if not bot_member.privileges:
            return await message.reply_text("❌ Bot is not an admin in that channel.")
    except Exception as e:
        return await message.reply_text(f"❌ Error checking admin status: {e}")

    save_channel_settings(channel_id, {
        "enabled": True,
        "owner_id": message.from_user.id,
        "channel_title": chat.title,
    })

    s = get_channel_settings(channel_id)
    fmt = s.get("format", "document")
    tmpl = s.get("template") or "Keep original filename"

    await message.reply_text(
        f"✅ Channel linked: {chat.title}\n\n"
        f"📁 Format: {fmt}\n"
        f"📝 Template: {tmpl}\n"
        f"🖼 Thumbnail: from your saved thumbnail\n"
        f"💬 Caption: original file caption (unchanged)\n\n"
        f"Commands:\n"
        f"/chformat {target} document — send as document\n"
        f"/chformat {target} video — send as video\n"
        f"/chtemplate {target} <template> — rename template\n\n"
        f"Every file posted will be auto-renamed! 🚀"
    )


@Client.on_message(filters.private & filters.command("removechannel"))
async def remove_channel(client: Client, message: Message):
    args = message.command
    if len(args) < 2:
        return await message.reply_text("❌ Usage: /removechannel <@username or channel_id>")
    try:
        chat = await client.get_chat(args[1])
        channel_id = chat.id
    except Exception as e:
        return await message.reply_text(f"❌ Channel not found: {e}")

    save_channel_settings(channel_id, {"enabled": False})
    await message.reply_text(f"✅ Auto-rename disabled for: {chat.title}")


@Client.on_message(filters.private & filters.command("chformat"))
async def set_ch_format(client: Client, message: Message):
    """Usage: /chformat <@channel> <document|video>"""
    args = message.command
    if len(args) < 3:
        return await message.reply_text(
            "❌ Usage: /chformat <@channel> <document|video>\n"
            "Example: /chformat @MyChannel video"
        )
    fmt = args[2].lower()
    if fmt not in ("document", "video"):
        return await message.reply_text("❌ Format must be 'document' or 'video'")
    try:
        chat = await client.get_chat(args[1])
        channel_id = chat.id
    except Exception as e:
        return await message.reply_text(f"❌ Channel not found: {e}")

    s = get_channel_settings(channel_id)
    if s.get("owner_id") != message.from_user.id:
        return await message.reply_text("❌ You didn't link this channel.")

    save_channel_settings(channel_id, {"format": fmt})
    await message.reply_text(f"✅ Channel format set to: {fmt}")


@Client.on_message(filters.private & filters.command("chtemplate"))
async def set_ch_template(client: Client, message: Message):
    """Usage: /chtemplate <@channel> <template>  — use {filename} {ext}"""
    args = message.text.split(None, 2)
    if len(args) < 3:
        return await message.reply_text(
            "❌ Usage: /chtemplate <@channel> <template>\n\n"
            "Placeholders: {filename} {ext}\n"
            "Example: /chtemplate @MyChannel {filename} [EchoFlix].{ext}\n"
            "Send 'off' to keep original filename."
        )
    target = args[1]
    template = args[2].strip()
    try:
        chat = await client.get_chat(target)
        channel_id = chat.id
    except Exception as e:
        return await message.reply_text(f"❌ Channel not found: {e}")

    s = get_channel_settings(channel_id)
    if s.get("owner_id") != message.from_user.id:
        return await message.reply_text("❌ You didn't link this channel.")

    val = None if template.lower() == "off" else template
    save_channel_settings(channel_id, {"template": val})
    await message.reply_text(
        f"✅ Channel template {'disabled' if not val else 'saved'}!"
        + (f"\n📝 Template: {val}" if val else "")
    )


@Client.on_message(filters.private & filters.command("mychannels"))
async def my_channels(client: Client, message: Message):
    uid = message.from_user.id
    channels = list(ch_col.find({"owner_id": uid, "enabled": True}))
    if not channels:
        return await message.reply_text("No channels linked.\nUse /addchannel to add one.")

    text = f"📡 Your linked channels ({len(channels)}):\n\n"
    for ch in channels:
        title = ch.get("channel_title", str(ch["_id"]))
        fmt = ch.get("format", "document")
        tmpl = ch.get("template") or "original filename"
        text += f"• {title}\n  Format: {fmt} | Template: {tmpl}\n\n"
    await message.reply_text(text)


# ─── Channel Post Handler ─────────────────────────────────────────────────────

@Client.on_message(filters.channel | (filters.group & (filters.document | filters.video | filters.audio)))
async def channel_auto_rename(client: Client, message: Message):
    channel_id = message.chat.id
    s = get_channel_settings(channel_id)

    if not s.get("enabled"):
        return

    # Detect file
    file = None
    orig_name = None
    is_video = False

    if message.document:
        file = message.document
        orig_name = file.file_name or f"file_{file.file_unique_id}"
        is_video = False
    elif message.video:
        file = message.video
        orig_name = file.file_name or f"video_{file.file_unique_id}.mp4"
        is_video = True
    elif message.audio:
        file = message.audio
        orig_name = file.file_name or f"audio_{file.file_unique_id}.mp3"
        is_video = False
    else:
        return

    # Keep original caption exactly as-is
    original_caption = message.caption or None

    # Apply template if set
    template = s.get("template")
    new_name = apply_template(template, orig_name) if template else orig_name

    # Output format
    fmt = s.get("format", "document")
    send_as_video = (fmt == "video")

    # Get owner's thumbnail
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

    # Download file
    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{new_name}"

    try:
        c_time = time.time()
        path = await client.download_media(
            message=file,
            file_name=file_path,
        )
    except Exception as e:
        return

    # Apply metadata if enabled
    final_path = path
    if use_metadata and metadata_code:
        os.makedirs("Metadata", exist_ok=True)
        metadata_path = f"Metadata/{new_name}"
        try:
            await add_metadata(path, metadata_path, metadata_code, message)
            final_path = metadata_path
        except Exception:
            final_path = path

    # Rename file on disk
    if os.path.exists(final_path) and final_path != file_path:
        try:
            os.rename(final_path, file_path)
            final_path = file_path
        except Exception:
            pass

    # Download thumbnail
    if thumb_file_id:
        try:
            ph_path = await client.download_media(thumb_file_id)
            Image.open(ph_path).convert("RGB").save(ph_path)
            img = Image.open(ph_path)
            img = img.resize((320, 320))
            img.save(ph_path, "JPEG")
        except Exception:
            ph_path = None

    # Upload with original caption + new thumbnail
    c_time = time.time()
    try:
        if send_as_video:
            await client.send_video(
                chat_id=channel_id,
                video=final_path,
                file_name=new_name,
                thumb=ph_path,
                supports_streaming=True,
                caption=original_caption,
                parse_mode=None if not original_caption else "html",
            )
        else:
            await client.send_document(
                chat_id=channel_id,
                document=final_path,
                file_name=new_name,
                thumb=ph_path,
                caption=original_caption,
                parse_mode=None if not original_caption else "html",
            )

        await asyncio.sleep(1)
        try:
            await client.delete_messages(channel_id, message.id)
        except Exception:
            pass  # Bot may not have delete permission in groups

    except Exception as e:
        pass

    finally:
        for p in [final_path, ph_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
