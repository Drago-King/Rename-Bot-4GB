from pyrogram.types import (InlineKeyboardButton, InlineKeyboardMarkup)
from pyrogram import Client, filters
from script import *
from config import *


@Client.on_callback_query(filters.regex('about'))
async def about(bot, update):
    text = script.ABOUT_TXT.format(bot.me.mention)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="home")]
    ])
    await update.message.edit(text=text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex('help'))
async def help(bot, update):
    text = script.HELP_TXT.format(update.from_user.mention)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('🖼 Thumbnail', callback_data='thumbnail'),
         InlineKeyboardButton('✏️ Caption', callback_data='caption')],
        [InlineKeyboardButton('🏠 Home', callback_data='home')],
    ])
    await update.message.edit(text=text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex('thumbnail'))
async def thumbnail(bot, update):
    text = script.THUMBNAIL_TXT
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help")]
    ])
    await update.message.edit(text=text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex('caption'))
async def caption(bot, update):
    text = script.CAPTION_TXT
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="help")]
    ])
    await update.message.edit(text=text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex('home'))
async def home_callback_handler(bot, query):
    text = f"""Hello {query.from_user.mention} 👋

➻ This Is An Advanced File Rename Bot.

➻ Rename & Change Thumbnail Of Your Files.

➻ Convert Video ↔️ Document.

➻ Auto Rename Files In Your Channel.

<b>Bot By <a href='https://t.me/Poseidon_xd'>Aqil</a></b>"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠️ Help", callback_data='help'),
         InlineKeyboardButton("❤️ About", callback_data='about')],
    ])
    await query.message.edit_text(text=text, reply_markup=keyboard)


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
