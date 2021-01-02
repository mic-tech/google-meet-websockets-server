#!/usr/bin/env python

import asyncio
import json
import logging
import websockets
import time
import webbrowser
from extension_tab import ExtensionTab

logging.basicConfig()

clients = set()
extension_tabs = {}


async def register_client(websocket):
    clients.add(websocket)


async def unregister_client(websocket):
    clients.remove(websocket)


def get_extension_tab():
    first_tab_id = None
    for tab_id in extension_tabs:
        if first_tab_id is None:
            first_tab_id = tab_id
        if extension_tabs[tab_id].isPrimary:
            return extension_tabs[tab_id]
    if first_tab_id is not None:
        return extension_tabs[first_tab_id]
    return None


async def handle_client_message(websocket, message):
    if not message or not websocket:
        return

    extension_tab = get_extension_tab()

    if message.get("action", None) == "getState":
        await websocket.send(json.dumps({
            "subject": "state",
            "message": extension_tab.state if extension_tab else None
        }))
    elif message.get("action", None) == "openGoogleMeetInBrowser":
        if not extension_tab:
            webbrowser.open("https://meet.google.com/")
    else:
        if extension_tab:
            await extension_tab.send_message(message)


async def extension_prune_inactive():
    while True:
        await asyncio.sleep(5)

        current_time = time.time()
        to_prune = []
        for tab_id in extension_tabs:
            if extension_tabs[tab_id].websocket is None and \
                    (current_time -
                     extension_tabs[tab_id].last_message_timestamp) > 30.0:
                # inactive tab, remove it
                to_prune.append(tab_id)
        for tab_id in to_prune:
            extension_tabs.pop(tab_id, None)

        extension_tab = get_extension_tab()
        if extension_tab:
            extension_tab.isPrimary = True


async def serve_extension(websocket, sender_id=None):
    if sender_id is None:
        return

    if sender_id not in extension_tabs:
        extension_tabs[sender_id] = ExtensionTab(websocket, sender_id)
    else:
        await extension_tabs[sender_id].websocket_opened(websocket)

    if len(extension_tabs) == 1:
        extension_tabs[sender_id].isPrimary = True

    try:
        async for msg in websocket:
            try:
                data = json.loads(msg)
                await extension_tabs[sender_id].handle_message(
                    data.get("subject", None),
                    data.get("message", None), clients
                )
            except json.JSONDecodeError:
                logging.error("invalid JSON received, ignoring.")
            except Exception as exp:
                logging.error(str(exp), exc_info=True)

    finally:
        await extension_tabs[sender_id].websocket_closed()


async def serve_client(websocket):
    await register_client(websocket)
    try:
        async for msg in websocket:
            try:
                await handle_client_message(websocket, json.loads(msg))
            except json.JSONDecodeError:
                logging.error("invalid JSON received, ignoring.")
            except Exception as exp:
                logging.error(str(exp), exc_info=True)

    except Exception as exp:
        logging.error(str(exp), exc_info=True)
    finally:
        await unregister_client(websocket)


async def serve_websocket(websocket, path):
    try:
        connected_msg = await websocket.recv()
        data = json.loads(connected_msg)

        if data.get("subject", None) == "connected" and \
                data.get("message", None) is not None:

            msg = data.get("message", None)
            if msg.get("type", None) == "extension":
                await serve_extension(websocket, msg.get("id", None))
            elif msg.get("type", None) == "client":
                await serve_client(websocket)

        else:
            await websocket.close()
            logging.error("unsupported websocket connection")

    except Exception as exp:
        logging.error(str(exp), exc_info=True)


start_websocket_server = websockets.serve(serve_websocket, "localhost", 8080)

asyncio.get_event_loop().run_until_complete(start_websocket_server)
asyncio.get_event_loop().run_until_complete(extension_prune_inactive())
asyncio.get_event_loop().run_forever()
