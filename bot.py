import pyromod.listen
from pyrogram import Client, idle
from plugins.cb_data import app as Client2
from config import *
import pyrogram.utils
import asyncio

pyrogram.utils.MIN_CHAT_ID = -999999999999
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999

bot = Client("Renamer", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH, plugins=dict(root='plugins'))

if STRING_SESSION:
    apps = [Client2, bot]
    for app in apps:
        app.start()
    # Start queue worker after bot is running
    loop = asyncio.get_event_loop()
    from plugins.channel_rename import _queue_worker
    loop.create_task(_queue_worker())
    idle()
    for app in apps:
        app.stop()
else:
    bot.start()
    loop = asyncio.get_event_loop()
    from plugins.channel_rename import _queue_worker
    loop.create_task(_queue_worker())
    idle()
    bot.stop()
