import pyromod.listen
from pyrogram import Client, idle
from plugins.cb_data import app as Client2
from config import *
import pyrogram.utils
import asyncio

pyrogram.utils.MIN_CHAT_ID = -999999999999
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999

bot = Client("Renamer", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH, plugins=dict(root='plugins'))


async def main():
    from plugins.channel_rename import _queue_worker
    asyncio.create_task(_queue_worker())

    if STRING_SESSION:
        await Client2.start()
        await bot.start()
        await idle()
        await bot.stop()
        await Client2.stop()
    else:
        await bot.start()
        await idle()
        await bot.stop()


asyncio.run(main())
