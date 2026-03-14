import time, datetime
from pyrogram import Client, filters
from pyrogram.types import (InlineKeyboardButton, InlineKeyboardMarkup)
from helper.database import find_one, used_limit, uploadlimit, usertype
from helper.database import daily as daily_
from datetime import datetime as dt
from datetime import date as date_
from helper.progress import humanbytes
from helper.date import check_expi
from config import ADMIN


@Client.on_message(filters.private & filters.command(["myplan"]))
async def myplan(client, message):
    uid = message.from_user.id

    # Admin gets unlimited
    if uid == ADMIN:
        await message.reply(
            f"<b>User ID:</b> <code>{uid}</code>\n"
            f"<b>Name:</b> {message.from_user.mention}\n\n"
            f"<b>🏷 Plan:</b> Admin\n\n"
            f"✓ Unlimited file size\n"
            f"✓ No daily limit\n"
            f"✓ No flood control\n"
            f"✓ All features unlocked",
            quote=True
        )
        return

    used_ = find_one(uid)
    daily = used_["daily"]
    expi = daily - int(time.mktime(time.strptime(str(date_.today()), '%Y-%m-%d')))
    if expi != 0:
        today = date_.today()
        epcho = int(time.mktime(time.strptime(str(today), '%Y-%m-%d')))
        daily_(uid, epcho)
        used_limit(uid, 0)

    _newus = find_one(uid)
    used = _newus["used_limit"]
    limit = _newus["uploadlimit"]
    remain = int(limit) - int(used)
    user = _newus["usertype"]
    ends = _newus["prexdate"]

    if ends:
        if not check_expi(ends):
            uploadlimit(uid, 2147483652)
            usertype(uid, "Free")
            ends = None

    if ends is None:
        text = (
            f"<b>User ID:</b> <code>{uid}</code>\n"
            f"<b>Name:</b> {message.from_user.mention}\n\n"
            f"<b>🏷 Plan:</b> {user}\n\n"
            f"✓ Daily Upload: {humanbytes(limit)}\n"
            f"✓ Used Today: {humanbytes(used)}\n"
            f"✓ Remaining: {humanbytes(remain)}\n\n"
            f"<b>Validity:</b> Lifetime"
        )
    else:
        normal_date = dt.fromtimestamp(ends).strftime('%Y-%m-%d')
        text = (
            f"<b>User ID:</b> <code>{uid}</code>\n"
            f"<b>Name:</b> {message.from_user.mention}\n\n"
            f"<b>🏷 Plan:</b> {user}\n\n"
            f"✓ Daily Upload: {humanbytes(limit)}\n"
            f"✓ Used Today: {humanbytes(used)}\n"
            f"✓ Remaining: {humanbytes(remain)}\n\n"
            f"<b>Plan Ends On:</b> {normal_date}"
        )

    kb = [[InlineKeyboardButton("💳 Upgrade", callback_data="upgrade"),
           InlineKeyboardButton("✖️ Cancel", callback_data="cancel")]]
    if user != "Free":
        kb = [[InlineKeyboardButton("✖️ Cancel", callback_data="cancel")]]

    await message.reply(text, quote=True, reply_markup=InlineKeyboardMarkup(kb))
