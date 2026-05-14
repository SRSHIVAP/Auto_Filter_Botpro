import os
import plugins.monkey_patch
import sys
from pyrogram import Client, idle, __version__
from pyrogram.raw.all import layer
import time
from pyrogram.errors import FloodWait
import asyncio
from datetime import date, datetime
from pathlib import Path
import importlib.util
import pytz
from aiohttp import web
from database.ia_filterdb import Media, Media2
from database.users_chats_db import db
from info import *
from utils import temp
from Script import script
from plugins import web_server, check_expired_premium, keep_alive
from dreamxbotz.Bot import dreamxbotz
from dreamxbotz.util.keepalive import ping_server
from dreamxbotz.Bot.clients import initialize_clients
from PIL import Image
Image.MAX_IMAGE_PIXELS = 500_000_000

import logging
import logging.config

logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.WARNING)

botStartTime = time.time()

def dreamxbotz_plugins_handler(app, plugins_dir: str | Path = "plugins", package_name: str = "plugins") -> list[str]:
    plugins_dir = Path(plugins_dir)
    loaded_plugins: list[str] = []

    if not plugins_dir.exists():
        logging.warning("Plugins Directory '%s' Does Not Exist.", plugins_dir)
        return loaded_plugins

    for file in sorted(plugins_dir.rglob("*.py")):
        if file.name == "__init__.py":
            continue

        rel_path = file.relative_to(plugins_dir).with_suffix("")
        import_path = package_name + ".".join([""] + list(rel_path.parts))

        try:
            spec = importlib.util.spec_from_file_location(import_path, file)
            if spec is None or spec.loader is None:
                logging.warning("Skipping %s (No Spec/Loader).", file)
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules[import_path] = module
            loaded_plugins.append(import_path)

            short_name = import_path.removeprefix(f"{package_name}.")
            logging.info("🔌 Loaded plugin: %s", short_name)

        except Exception:
            logging.exception("Failed To Import Plugin: %s", import_path)

    disp = getattr(app, "dispatcher", None)
    if disp is None:
        logging.warning("App Has No Dispatcher; Skipping Handler Regroup.")
        return loaded_plugins

    if 0 in disp.groups:
        all_handlers = list(disp.groups[0])
        for i, handler in enumerate(all_handlers):
            disp.remove_handler(handler, group=0)
            disp.add_handler(handler, group=i)
    else:
        logging.info("No Handlers In Group 0; Nothing To Regroup.")

    return loaded_plugins


async def dreamxbotz_start():
    print('\n\nInitalizing DreamxBotz')
    await dreamxbotz.start()
    bot_info = await dreamxbotz.get_me()
    dreamxbotz.username = bot_info.username
    await initialize_clients()
    loaded_plugins = dreamxbotz_plugins_handler(dreamxbotz)
    if loaded_plugins:
        logging.info("✅ Plugins Loaded: %d", len(loaded_plugins))
    else:
        logging.info("⚠️ No Plugins Loaded.")
    if ON_HEROKU:
        asyncio.create_task(ping_server())
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats
    await Media.ensure_indexes()
    if MULTIPLE_DB:
        await Media2.ensure_indexes()
        print("Multiple Database Mode On. Now Files Will Be Save In Second DB If First DB Is Full")
    else:
        print("Single DB Mode On ! Files Will Be Save In First Database")
    me = await dreamxbotz.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    temp.B_LINK = me.mention
    dreamxbotz.username = '@' + me.username
    dreamxbotz.loop.create_task(check_expired_premium(dreamxbotz))
    logging.info(f"{me.first_name} with Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
    logging.info(LOG_STR)
    logging.info(script.LOGO)
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    current_time = now.strftime("%H:%M:%S %p")
    await dreamxbotz.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(temp.B_LINK, today, current_time))

    # Web server setup — INSIDE the async function
    bind_address = "0.0.0.0"
    PORT = int(os.environ.get("PORT", 8000))
    app = web.AppRunner(await web_server())
    await app.setup()
    site = web.TCPSite(app, bind_address, PORT)
    await site.start()

    dreamxbotz.loop.create_task(keep_alive())
    await idle()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    while True:
        try:
            loop.run_until_complete(dreamxbotz_start())
            break
        except FloodWait as e:
            print(f"FloodWait! Sleeping for {e.value} seconds.")
            time.sleep(e.value)
        except KeyboardInterrupt:
            logging.info('Service Stopped Bye 👋')
            break
