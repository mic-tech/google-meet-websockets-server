import asyncio
import json
import time


class ExtensionTab:
    def __init__(self, websocket, tabId=None, state=None):
        self.websocket = websocket
        self.tabId = tabId
        self.state = state
        self.last_alive_timestamp = time.time()
        self.isPrimary = False

    async def websocket_opened(self, websocket):
        self.last_alive_timestamp = time.time()
        self.websocket = websocket

    async def websocket_closed(self):
        self.websocket = None

    async def send_message(self, message):
        if message is None or self.websocket is None:
            return
        await self.websocket.send(json.dumps(message))

    async def handle_message(self, subject, message, clients):
        if self.isPrimary:
            client_msg = json.dumps({
                "subject": subject,
                "message": message
            })
            if len(clients) > 0:
                await asyncio.wait([
                    asyncio.create_task(client_socket.send(client_msg))
                    for client_socket in clients
                ])

        if subject == "state":
            self.state = message
