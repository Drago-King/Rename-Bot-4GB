from helper.progress import progress_for_pyrogram
from pyrogram import Client, filters
from pyrogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, ForceReply)
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.database import *
import os, random, time, asyncio, humanize
from PIL import Image
from datetime import timedelta
from helper.ffmpeg import take_screen_shot, fix_thumb, add_metadata
from helper.progress import humanbytes
from helper.set import escape_invalid_curly_brackets
from config import *

# Only create user client if STRING_SESSION is set
if STRING_SESSION:
    app = Client("JishuBotz", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
else:
    app = None


@Client.on_callback_query(filters.regex('cancel'))
async def cancel(bot, update):
    try:
        await update.message.delete()
        await update.message.reply_to_message.delete()
        await update.message.continue_propagation()
    except:
        await update.message.delete()
        await update.message.continue_propagation()
        return


@Client.on_callback_query(filters.regex('rename'))
async def rename(bot, update):
    date_fa = str(update.message.date)
    pattern = '%Y-%m-%d %H:%M:%S'
    date = int(time.mktime(time.strptime(date_fa, pattern)))
    chat_id = update.message.chat.id
    id = update.message.reply_to_message_id
    await update.message.delete()
    await update.message.reply_text(
        f"__Please Enter The New Filename...__\n\n**Note :** Extension Not Required",
        reply_to_message_id=id,
        reply_markup=ForceReply(True)
    )
    dateupdate(chat_id, date)


def get_thumb(thumb_path):
    """Fix thumbnail properly."""
    try:
        img = Image.open(thumb_path).convert("RGB")
        img = img.resize((320, 320))
        img.save(thumb_path, "JPEG")
        return thumb_path
    except Exception:
        return None


@Client.on_callback_query(filters.regex("doc"))
async def doc(bot, update):
    os.makedirs("Metadata", exist_ok=True)
    os.makedirs("downloads", exist_ok=True)

    new_name = update.message.text
    used_ = find_one(update.from_user.id)
    used = used_["used_limit"]
    new_filename = new_name.split(":-")[1].strip()
    file_path = f"downloads/{new_filename}"
    message = update.message.reply_to_message
    file = message.document or message.video or message.audio
    ms = await update.message.edit("🚀 Downloading...  ⚡")
    c_time = time.time()
    total_used = used + int(file.file_size)
    used_limit(update.from_user.id, total_used)

    os.makedirs("downloads", exist_ok=True)
    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Downloading...  ⚡", ms, c_time)
        )
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
        return

    if not path or not os.path.exists(path):
        await ms.edit("❌ Download failed.")
        return

    # Metadata
    _bool_metadata = find(int(message.chat.id))[2]
    metadata_path = f"Metadata/{new_filename}"
    if _bool_metadata:
        metadata = find(int(message.chat.id))[3]
        await add_metadata(path, metadata_path, metadata, ms)
    else:
        await ms.edit("🚀 Processing...  ⚡")

    final_path = metadata_path if _bool_metadata and os.path.exists(metadata_path) else path

    # Caption
    user_id = int(update.message.chat.id)
    data = find(user_id)
    c_caption = data[1] if data else None
    thumb = data[0] if data else None

    if c_caption:
        doc_list = ["filename", "filesize"]
        new_tex = escape_invalid_curly_brackets(c_caption, doc_list)
        caption = new_tex.format(filename=new_filename, filesize=humanbytes(file.file_size))
    else:
        caption = f"**{new_filename}**"

    # Thumbnail
    ph_path = None
    if thumb:
        try:
            ph_path = await bot.download_media(thumb)
            ph_path = get_thumb(ph_path)
        except Exception:
            ph_path = None

    # Upload
    await ms.edit("🚀 Uploading...  ⚡")
    c_time = time.time()
    try:
        # Use user client for large files only if available and needed
        if app and file.file_size > 2090000000:
            filw = await app.send_document(
                LOG_CHANNEL, document=final_path, thumb=ph_path,
                caption=caption, progress=progress_for_pyrogram,
                progress_args=("🚀 Uploading...  ⚡", ms, c_time)
            )
            await bot.copy_message(update.from_user.id, filw.chat.id, filw.id)
            await ms.delete()
        else:
            await bot.send_document(
                update.from_user.id, document=final_path, thumb=ph_path,
                caption=caption, progress=progress_for_pyrogram,
                progress_args=("🚀 Uploading...  ⚡", ms, c_time)
            )
            await ms.delete()
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
    finally:
        for p in [final_path, ph_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass


@Client.on_callback_query(filters.regex("vid"))
async def vid(bot, update):
    os.makedirs("Metadata", exist_ok=True)
    os.makedirs("downloads", exist_ok=True)

    new_name = update.message.text
    used_ = find_one(update.from_user.id)
    used = used_["used_limit"]
    new_filename = new_name.split(":-")[1].strip()
    file_path = f"downloads/{new_filename}"
    message = update.message.reply_to_message
    file = message.document or message.video or message.audio
    ms = await update.message.edit("🚀 Downloading...  ⚡")
    c_time = time.time()
    total_used = used + int(file.file_size)
    used_limit(update.from_user.id, total_used)

    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Downloading...  ⚡", ms, c_time)
        )
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
        return

    if not path or not os.path.exists(path):
        await ms.edit("❌ Download failed.")
        return

    # Metadata
    _bool_metadata = find(int(message.chat.id))[2]
    metadata_path = f"Metadata/{new_filename}"
    if _bool_metadata:
        metadata = find(int(message.chat.id))[3]
        await add_metadata(path, metadata_path, metadata, ms)
    else:
        await ms.edit("🚀 Processing...  ⚡")

    final_path = metadata_path if _bool_metadata and os.path.exists(metadata_path) else path

    # Duration
    duration = 0
    try:
        meta = extractMetadata(createParser(final_path))
        if meta and meta.has("duration"):
            duration = meta.get('duration').seconds
    except Exception:
        pass

    # Caption
    user_id = int(update.message.chat.id)
    data = find(user_id)
    c_caption = data[1] if data else None
    thumb = data[0] if data else None

    if c_caption:
        vid_list = ["filename", "filesize", "duration"]
        new_tex = escape_invalid_curly_brackets(c_caption, vid_list)
        caption = new_tex.format(
            filename=new_filename,
            filesize=humanbytes(file.file_size),
            duration=timedelta(seconds=duration)
        )
    else:
        caption = f"**{new_filename}**"

    # Thumbnail
    ph_path = None
    if thumb:
        try:
            ph_path = await bot.download_media(thumb)
            ph_path = get_thumb(ph_path)
        except Exception:
            ph_path = None
    else:
        try:
            ph_path_ = await take_screen_shot(
                final_path,
                os.path.dirname(os.path.abspath(final_path)),
                random.randint(0, max(duration - 1, 0))
            )
            width, height, ph_path = await fix_thumb(ph_path_)
        except Exception:
            ph_path = None

    # Upload
    await ms.edit("🚀 Uploading...  ⚡")
    c_time = time.time()
    try:
        if app and file.file_size > 2090000000:
            filw = await app.send_video(
                LOG_CHANNEL, video=final_path, thumb=ph_path, duration=duration,
                caption=caption, progress=progress_for_pyrogram,
                progress_args=("🚀 Uploading...  ⚡", ms, c_time)
            )
            await bot.copy_message(update.from_user.id, filw.chat.id, filw.id)
            await ms.delete()
        else:
            await bot.send_video(
                update.from_user.id, video=final_path, thumb=ph_path,
                duration=duration, caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("🚀 Uploading...  ⚡", ms, c_time)
            )
            await ms.delete()
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
    finally:
        for p in [final_path, ph_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass


@Client.on_callback_query(filters.regex("aud"))
async def aud(bot, update):
    os.makedirs("Metadata", exist_ok=True)
    os.makedirs("downloads", exist_ok=True)

    new_name = update.message.text
    used_ = find_one(update.from_user.id)
    used = used_["used_limit"]
    new_filename = new_name.split(":-")[1].strip()
    file_path = f"downloads/{new_filename}"
    message = update.message.reply_to_message
    file = message.document or message.video or message.audio
    ms = await update.message.edit("🚀 Downloading...  ⚡")
    c_time = time.time()
    total_used = used + int(file.file_size)
    used_limit(update.from_user.id, total_used)

    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Downloading...  ⚡", ms, c_time)
        )
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
        return

    if not path or not os.path.exists(path):
        await ms.edit("❌ Download failed.")
        return

    # Metadata
    _bool_metadata = find(int(message.chat.id))[2]
    metadata_path = f"Metadata/{new_filename}"
    if _bool_metadata:
        metadata = find(int(message.chat.id))[3]
        await add_metadata(path, metadata_path, metadata, ms)
    else:
        await ms.edit("🚀 Processing...  ⚡")

    final_path = metadata_path if _bool_metadata and os.path.exists(metadata_path) else path

    # Duration
    duration = 0
    try:
        meta = extractMetadata(createParser(final_path))
        if meta and meta.has("duration"):
            duration = meta.get('duration').seconds
    except Exception:
        pass

    # Caption
    user_id = int(update.message.chat.id)
    data = find(user_id)
    c_caption = data[1] if data else None
    thumb = data[0] if data else None

    if c_caption:
        aud_list = ["filename", "filesize", "duration"]
        new_tex = escape_invalid_curly_brackets(c_caption, aud_list)
        caption = new_tex.format(
            filename=new_filename,
            filesize=humanbytes(file.file_size),
            duration=timedelta(seconds=duration)
        )
    else:
        caption = f"**{new_filename}**"

    # Thumbnail
    ph_path = None
    if thumb:
        try:
            ph_path = await bot.download_media(thumb)
            ph_path = get_thumb(ph_path)
        except Exception:
            ph_path = None

    # Upload
    await ms.edit("🚀 Uploading...  ⚡")
    c_time = time.time()
    try:
        await bot.send_audio(
            update.message.chat.id, audio=final_path,
            caption=caption, thumb=ph_path, duration=duration,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Uploading...  ⚡", ms, c_time)
        )
        await ms.delete()
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
    finally:
        for p in [final_path, ph_path]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass
