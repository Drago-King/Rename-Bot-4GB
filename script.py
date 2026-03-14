class script(object):
    HELP_TXT = """<b>Hey</b> {}

<b>Here Are The Available Commands:</b>

<b>⦿ /rename</b> - Send a file to rename it
<b>⦿ /addthumb</b> - Send a photo to set thumbnail
<b>⦿ /viewthumb</b> - View your saved thumbnail
<b>⦿ /delthumb</b> - Delete your thumbnail
<b>⦿ /set_caption</b> - Set custom caption
<b>⦿ /see_caption</b> - View your caption
<b>⦿ /del_caption</b> - Delete your caption
<b>⦿ /metadata</b> - Set metadata for files
<b>⦿ /addchannel</b> - Link a channel for auto-rename
<b>⦿ /removechannel</b> - Unlink a channel
<b>⦿ /chformat</b> - Set channel output format
<b>⦿ /chtemplate</b> - Set channel rename template"""

    CAPTION_TXT = """<b><u>📝 HOW TO SET CAPTION</u></b>

<b>⦿ /set_caption</b> - Set your caption
<b>⦿ /see_caption</b> - View your caption
<b>⦿ /del_caption</b> - Delete your caption

<b>Placeholders:</b>
<code>{filename}</code> - File name
<code>{filesize}</code> - File size
<code>{duration}</code> - Duration (video/audio)"""

    THUMBNAIL_TXT = """<b><u>🖼️ HOW TO SET THUMBNAIL</u></b>

<b>⦿ Simply send a photo to set it as thumbnail</b>

<b>⦿ /viewthumb</b> - View your thumbnail
<b>⦿ /delthumb</b> - Delete your thumbnail"""

    ABOUT_TXT = """<b>🤖 Bot:</b> {}
<b>📝 Language:</b> <a href='https://python.org'>Python 3</a>
<b>📚 Library:</b> <a href='https://pyrogram.org'>Pyrogram 2.0</a>
<b>🧑‍💻 Owner:</b> <a href='https://t.me/Poseidon_xd'>Aqil</a>"""

    DONATE_TXT = """<b>Contact owner for premium plans.</b>

<b>🧑‍💻 Owner:</b> <a href='https://t.me/Poseidon_xd'>Aqil</a>"""

    ADMIN_TXT = """<b><u>🦋 ADMIN COMMANDS</u></b>

<b>⦿ /users</b> - Total users
<b>⦿ /allids</b> - All user IDs
<b>⦿ /broadcast</b> - Broadcast a message
<b>⦿ /warn</b> - Warn a user
<b>⦿ /resetpower</b> - Reset user power
<b>⦿ /ceasepower</b> - Cease user power
<b>⦿ /addpremium</b> - Add premium to user
<b>⦿ /restart</b> - Restart the bot"""

    METADATA_TXT = """<b><u>🖼️ SET CUSTOM METADATA</u></b>

Send your metadata text below.

Example: <code>@Poseidon_xd</code>"""
