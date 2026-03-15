from datetime import date as date_
import os, datetime, asyncio, time, humanize
from script import *
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram import Client, filters
from pyrogram.types import (InlineKeyboardButton, InlineKeyboardMarkup)
from helper.progress import humanbytes
from helper.database import botdata, find_one, total_user
from helper.database import insert, find_one, used_limit, usertype, uploadlimit, addpredata, total_rename, total_size
from pyrogram.file_id import FileId
from helper.database import daily as daily_
from helper.date import check_expi
from config import *

token = BOT_TOKEN
botid = token.split(':')[0]


@Client.on_message(filters.private & filters.command(["start"]))
async def start(client, message):
    user_id = message.chat.id
    insert(int(user_id))

    loading_sticker_message = await message.reply_sticker("CAACAgIAAxkBAALmzGXSSt3ppnOsSl_spnAP8wHC26jpAAJEGQACCOHZSVKp6_XqghKoHgQ")
    await asyncio.sleep(2)
    await loading_sticker_message.delete()

    text = f"""Hello {message.from_user.mention} 👋

➻ This Is An Advanced File Rename Bot.

➻ Rename & Change Thumbnail Of Your Files.

➻ Convert Video ↔️ Document.

➻ Auto Rename Files In Your Channel.

<b>Bot By <a href='https://t.me/Poseidon_xd'>Aqil</a></b>"""

    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠️ Help", callback_data='help'),
         InlineKeyboardButton("❤️ About", callback_data='about')],
    ])

    await message.reply_photo(
        photo=START_PIC,
        caption=text,
        reply_markup=button,
        quote=True
    )


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def send_doc(client, message):
    user_id = message.from_user.id
    insert(int(user_id))

    # Skip if autorename is active
    try:
        from plugins.autorename import get_ar
        if get_ar(user_id).get("enabled"):
            return
    except Exception:
        pass

    # Force sub check
    if FORCE_SUBS:
        try:
            await client.get_chat_member(FORCE_SUBS, user_id)
        except UserNotParticipant:
            await message.reply_text(
                "<b>Please join my channel to use this bot.</b>",
                reply_to_message_id=message.id,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔺 Join Channel", url=f"https://t.me/{FORCE_SUBS}")]
                ]))
            return

    botdata(int(botid))
    bot_data = find_one(int(botid))
    prrename = bot_data['total_rename']
    prsize = bot_data['total_size']

    media = await client.get_messages(message.chat.id, message.id)
    file = media.document or media.video or media.audio
    dcid = FileId.decode(file.file_id).dc_id
    filename = file.file_name
    filesize = humanize.naturalsize(file.file_size)

    # ── Admin bypasses ALL limits ──────────────────────────────────────────────
    if user_id == ADMIN:
        total_rename(int(botid), prrename)
        total_size(int(botid), prsize, file.file_size)
        await message.reply_text(
            f"__What Do You Want Me To Do With This File ?__\n\n"
            f"**File Name :** `{filename}`\n"
            f"**File Size :** {filesize}\n"
            f"**DC ID :** {dcid}",
            reply_to_message_id=message.id,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Rename", callback_data="rename"),
                 InlineKeyboardButton("✖️ Cancel", callback_data="cancel")]
            ])
        )
        return

    # ── Normal user flow ───────────────────────────────────────────────────────
    user_deta = find_one(user_id)
    used_date = user_deta["date"]
    buy_date = user_deta["prexdate"]
    daily = user_deta["daily"]
    user_type = user_deta["usertype"]

    c_time = time.time()
    LIMIT = 10 if user_type != "Free" else 120
    then = used_date + LIMIT
    left = round(then - c_time)

    if left > 0:
        ltime = str(datetime.timedelta(seconds=left))
        await message.reply_text(
            f"<b>⏳ Please wait {ltime}</b>",
            reply_to_message_id=message.id
        )
        return

    used_ = find_one(user_id)
    used = used_["used_limit"]
    limit = used_["uploadlimit"]
    expi = daily - int(time.mktime(time.strptime(str(date_.today()), '%Y-%m-%d')))
    if expi != 0:
        today = date_.today()
        epcho = int(time.mktime(time.strptime(str(today), '%Y-%m-%d')))
        daily_(user_id, epcho)
        used_limit(user_id, 0)
        used = 0

    remain = limit - used
    if remain < int(file.file_size):
        await message.reply_text(
            f"Daily limit exhausted.\n\n"
            f"<b>File Size:</b> {humanbytes(file.file_size)}\n"
            f"<b>Used:</b> {humanbytes(used)}\n"
            f"<b>Remaining:</b> {humanbytes(remain)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Upgrade", callback_data="upgrade")]
            ])
        )
        return

    value = 2147483648
    if value < file.file_size:
        if STRING_SESSION and buy_date:
            from helper.date import check_expi
            if check_expi(buy_date):
                total_rename(int(botid), prrename)
                total_size(int(botid), prsize, file.file_size)
                await message.reply_text(
                    f"__What Do You Want Me To Do With This File ?__\n\n"
                    f"**File Name :** `{filename}`\n**File Size :** {filesize}\n**DC ID :** {dcid}",
                    reply_to_message_id=message.id,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Rename", callback_data="rename"),
                         InlineKeyboardButton("✖️ Cancel", callback_data="cancel")]
                    ])
                )
            else:
                uploadlimit(user_id, 2147483648)
                usertype(user_id, "Free")
                await message.reply_text(f'Your plan expired on {buy_date}', quote=True)
        else:
            await message.reply_text(
                "Files over 2GB require a premium plan.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Upgrade", callback_data="upgrade")]
                ])
            )
        return

    if buy_date:
        from helper.date import check_expi
        if not check_expi(buy_date):
            uploadlimit(user_id, 2147483648)
            usertype(user_id, "Free")

    total_rename(int(botid), prrename)
    total_size(int(botid), prsize, file.file_size)
    await message.reply_text(
        f"__What Do You Want Me To Do With This File ?__\n\n"
        f"**File Name :** `{filename}`\n**File Size :** {filesize}\n**DC ID :** {dcid}",
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Rename", callback_data="rename"),
             InlineKeyboardButton("✖️ Cancel", callback_data="cancel")]
        ])
    )
