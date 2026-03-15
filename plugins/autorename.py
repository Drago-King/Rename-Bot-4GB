# Auto-Rename Plugin
# /autorename on  — activates auto mode
# /autorename off — deactivates
# When active: any file sent/forwarded is auto-renamed using original caption
# Progress shown for download and upload
# Output: always document

import os
import re
import time
import asyncio
import pymongo
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image
from config import DATABASE_URL, DATABASE_NAME
from helper.progress import progress_for_pyrogram, humanbytes
from helper.ffmpeg import add_metadata
from helper.database import find

# ─── MongoDB ──────────────────────────────────────────────────────────────────
mongo = pymongo.MongoClient(DATABASE_URL)
db = mongo[DATABASE_NAME]
ar_col = db["autorename_settings"]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_ar(user_id: int) -> dict:
    doc = ar_col.find_one({"_id": user_id})
    if not doc:
        doc = {"_id": user_id, "enabled": False}
        ar_col.insert_one(doc)
    return doc

def set_ar(user_id: int, data: dict):
    ar_col.update_one({"_id": user_id}, {"$set": data}, upsert=True)

def sanitize_filename(text: str, orig_name: str) -> str:
    """Clean caption for use as filename, keep extension from original."""
    if not text:
        return orig_name

    # Get extension from original file
    _, ext = os.path.splitext(orig_name)

    # Use only first line
    first_line = text.strip().splitlines()[0].strip()

    # Remove illegal filename chars
    clean = re.sub(r'[\\/*?:"<>|]', '', first_line)
    clean = re.sub(r'\s+', ' ', clean).strip()

    # Trim to 64 chars
    if len(clean) > 64:
        clean = clean[:64].strip()

    if not clean:
        return orig_name

    # Add extension if not already present
    if ext and not clean.lower().endswith(ext.lower()):
        clean = clean + ext

    return clean


# ─── Command ──────────────────────────────────────────────────────────────────

@Client.on_message(filters.private & filters.command("autorename"))
async def autorename_cmd(client: Client, message: Message):
    args = message.command
    uid = message.from_user.id

    if len(args) < 2 or args[1].lower() not in ("on", "off"):
        s = get_ar(uid)
        status = "✅ ON" if s.get("enabled") else "❌ OFF"
        return await message.reply_text(
            f"🔄 Auto-Rename Mode: {status}\n\n"
            f"Usage:\n"
            f"/autorename on  — activate\n"
            f"/autorename off — deactivate\n\n"
            f"When ON: send or forward any file and it will be\n"
            f"automatically renamed using the original caption.\n"
            f"No prompts needed!"
        )

    enable = args[1].lower() == "on"
    set_ar(uid, {"enabled": enable})

    if enable:
        await message.reply_text(
            "✅ Auto-Rename activated!\n\n"
            "Send or forward any file — I'll rename it\n"
            "using the original caption automatically.\n\n"
            "Send /autorename off to deactivate."
        )
    else:
        await message.reply_text("❌ Auto-Rename deactivated.")


# ─── File Handler ─────────────────────────────────────────────────────────────

@Client.on_message(
    filters.private & (filters.document | filters.video | filters.audio),
    group=2
)
async def autorename_handler(client: Client, message: Message):
    uid = message.from_user.id
    s = get_ar(uid)

    if not s.get("enabled"):
        return  # Let normal rename flow handle it

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

    if not file:
        return

    # Get caption — from forwarded message or current message
    caption = None
    if message.forward_from or message.forward_from_chat or message.forward_sender_name:
        caption = message.caption  # forwarded file caption
    else:
        caption = message.caption  # directly sent file caption

    new_name = sanitize_filename(caption, orig_name)

    # Get user's saved thumbnail
    data = find(uid)
    thumb_file_id = data[0] if data else None
    use_metadata = data[2] if data else False
    metadata_code = data[3] if data else None

    # Status message
    ms = await message.reply_text(
        f"⚙️ Auto-Rename Mode\n\n"
        f"📂 Original: `{orig_name}`\n"
        f"📁 New Name: `{new_name}`\n\n"
        f"📥 Starting download...",
        quote=True
    )

    os.makedirs("downloads", exist_ok=True)
    safe = new_name.replace("/", "_").replace("\0", "_")
    file_path = f"downloads/{int(time.time())}_{safe}"
    c_time = time.time()

    # Download
    try:
        path = await client.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("📥 Downloading...", ms, c_time)
        )
    except Exception as e:
        return await ms.edit(f"❌ Download failed: {e}")

    # Rename file on disk
    renamed_path = f"downloads/{int(time.time())}_renamed_{safe}"
    try:
        os.rename(path, renamed_path)
        final_path = renamed_path
    except Exception:
        final_path = path

    # Metadata
    if use_metadata and metadata_code:
        os.makedirs("Metadata", exist_ok=True)
        meta_path = f"Metadata/{int(time.time())}_{safe}"
        try:
            await add_metadata(final_path, meta_path, metadata_code, ms)
            final_path = meta_path
        except Exception:
            pass

    # Thumbnail
    ph_path = None
    if thumb_file_id:
        try:
            ph_path = await client.download_media(thumb_file_id)
            img = Image.open(ph_path).convert("RGB")
            img = img.resize((320, 320))
            img.save(ph_path, "JPEG")
        except Exception:
            ph_path = None

    # Upload as document
    await ms.edit(f"📤 Uploading `{new_name}`...")
    c_time = time.time()
    try:
        await client.send_document(
            chat_id=uid,
            document=final_path,
            file_name=new_name,
            thumb=ph_path,
            caption=f"**{new_name}**",
            progress=progress_for_pyrogram,
            progress_args=("📤 Uploading...", ms, c_time)
        )
        await ms.delete()
    except Exception as e:
        await ms.edit(f"❌ Upload failed: {e}")
    finally:
        for p in [final_path, ph_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
