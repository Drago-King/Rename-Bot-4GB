# Auto-Rename Plugin v4
# - Parallel processing (no queue)
# - Proper download handling (no .temp rename issues)
# - Large file support via user client

import os
import re
import time
import asyncio
import pymongo
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image
from config import DATABASE_URL, DATABASE_NAME, STRING_SESSION, API_ID, API_HASH, LOG_CHANNEL
from helper.progress import progress_for_pyrogram
from helper.ffmpeg import add_metadata
from helper.database import find

# ─── MongoDB ──────────────────────────────────────────────────────────────────
mongo = pymongo.MongoClient(DATABASE_URL)
db = mongo[DATABASE_NAME]
ar_col = db["autorename_settings"]

# ─── User client for >2GB ─────────────────────────────────────────────────────
_user_client = None
_user_client_lock = asyncio.Lock()

async def get_user_client():
    global _user_client
    if not STRING_SESSION:
        return None
    async with _user_client_lock:
        if _user_client is None:
            from pyrogram import Client as PC
            uc = PC("aruser", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
            try:
                await uc.start()
                _user_client = uc
                print("[AR] User client started ✅")
            except Exception as e:
                print(f"[AR] User client failed: {e}")
                return None
    return _user_client

# ─── DB ───────────────────────────────────────────────────────────────────────

def get_ar(uid: int) -> dict:
    doc = ar_col.find_one({"_id": uid})
    if not doc:
        doc = {"_id": uid, "enabled": False}
        ar_col.insert_one(doc)
    return doc

def set_ar(uid: int, data: dict):
    ar_col.update_one({"_id": uid}, {"$set": data}, upsert=True)

def sanitize(text: str, orig: str) -> str:
    if not text:
        return orig
    _, ext = os.path.splitext(orig)
    line = text.strip().splitlines()[0].strip()
    clean = re.sub(r'[\\/*?:"<>|]', '', line)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if len(clean) > 64:
        clean = clean[:64].strip()
    if not clean:
        return orig
    if ext and not clean.lower().endswith(ext.lower()):
        clean += ext
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
            f"🔄 Auto-Rename: {status}\n\n"
            f"/autorename on  — activate\n"
            f"/autorename off — deactivate\n\n"
            f"When ON: send or forward any file →\n"
            f"auto renamed using original caption."
        )

    enable = args[1].lower() == "on"
    set_ar(uid, {"enabled": enable})
    if enable:
        await message.reply_text(
            "✅ Auto-Rename ON!\n\n"
            "Send or forward files — I'll rename them\n"
            "using the original caption automatically.\n\n"
            "/autorename off to stop."
        )
    else:
        await message.reply_text("❌ Auto-Rename OFF.")

# ─── Core ─────────────────────────────────────────────────────────────────────

async def _do_autorename(client: Client, message: Message, uid: int):
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

    new_name = sanitize(message.caption, orig_name)

    data = find(uid)
    thumb_file_id = data[0] if data else None
    use_metadata = data[2] if data else False
    metadata_code = data[3] if data else None

    ms = await message.reply_text(
        f"⚙️ **Auto-Rename**\n\n"
        f"📂 `{orig_name}`\n"
        f"📁 → `{new_name}`\n\n"
        f"📥 Downloading...",
        quote=True
    )

    os.makedirs("downloads", exist_ok=True)
    # Use unique temp dir per file to avoid conflicts
    unique = f"{int(time.time())}_{uid}_{file.file_unique_id}"
    dl_dir = f"downloads/{unique}"
    os.makedirs(dl_dir, exist_ok=True)
    c_time = time.time()

    # Download — let pyrogram handle temp files in its own dir
    try:
        path = await client.download_media(
            message=file,
            file_name=f"{dl_dir}/{new_name}",
            progress=progress_for_pyrogram,
            progress_args=("📥 Downloading...", ms, c_time)
        )
    except Exception as e:
        return await ms.edit(f"❌ Download failed:\n`{e}`")

    if not path or not os.path.exists(path):
        return await ms.edit("❌ Download failed: file not found after download.")

    final_path = path

    # Metadata
    if use_metadata and metadata_code:
        os.makedirs("Metadata", exist_ok=True)
        meta_path = f"Metadata/{unique}_{new_name}"
        try:
            await add_metadata(final_path, meta_path, metadata_code, ms)
            if os.path.exists(meta_path):
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

    # Upload
    await ms.edit(f"📤 Uploading `{new_name}`...")
    c_time = time.time()
    file_size = os.path.getsize(final_path)

    try:
        if file_size > 2090000000 and STRING_SESSION and LOG_CHANNEL:
            uc = await get_user_client()
            if uc:
                filw = await uc.send_document(
                    chat_id=LOG_CHANNEL,
                    document=final_path,
                    file_name=new_name,
                    thumb=ph_path,
                    caption=f"**{new_name}**",
                    progress=progress_for_pyrogram,
                    progress_args=("📤 Uploading...", ms, c_time)
                )
                await client.copy_message(uid, filw.chat.id, filw.id)
                await ms.delete()
            else:
                await ms.edit("❌ Large file failed — check STRING_SESSION env var.")
        else:
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
        await ms.edit(f"❌ Upload failed:\n`{e}`")
    finally:
        # Clean up entire unique dir
        import shutil
        for p in [ph_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except Exception: pass
        try:
            shutil.rmtree(dl_dir, ignore_errors=True)
        except Exception:
            pass
        if final_path and os.path.exists(final_path) and dl_dir not in final_path:
            try: os.remove(final_path)
            except Exception: pass

# ─── Handler ──────────────────────────────────────────────────────────────────

@Client.on_message(
    filters.private & (filters.document | filters.video | filters.audio),
    group=2
)
async def autorename_handler(client: Client, message: Message):
    uid = message.from_user.id
    if not get_ar(uid).get("enabled"):
        return
    # Fire and forget — fully parallel, no queue
    asyncio.create_task(_do_autorename(client, message, uid))
