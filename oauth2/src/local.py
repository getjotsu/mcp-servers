import typing
import os
import asyncio
import json

from anyio import open_file
from mcp.shared.auth import OAuthClientInformationFull

from clients import ClientManager
from cache import AsyncCache


# All local implementations assume a single uvicorn server process.
# Multiple processes would require a database or Redis-like implementation.

class LocalClientManager(ClientManager):
    HOME = os.path.dirname(os.path.dirname(__file__))
    CLIENTS_FILE = os.path.join('../clients.json')

    def __init__(self):
        self.lock = asyncio.Lock()
        self.clients: typing.Dict[str, OAuthClientInformationFull] = {}
        try:
            with open(self.CLIENTS_FILE, 'r') as fp:
                for client_info in json.load(fp):
                    self.clients[client_info['client_id']] = OAuthClientInformationFull(**client_info)
        except (OSError, json.JSONDecodeError):
            pass

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients[client_id]

    async def save_client(self, client: OAuthClientInformationFull):
        self.clients[client.client_id] = client
        await self._save_clients()

    async def _save_clients(self):
        """
        Clients have to persist across server restarts, so save them in a simple JSON file in the root directory.
        """
        async with self.lock:
            try:
                async with await open_file(self.CLIENTS_FILE, 'w') as fp:
                    obj = [client.model_dump(mode='json') for client in self.clients.values()]
                    await fp.write(json.dumps(obj))
            except OSError:
                pass


# Sessions don't need to persist across restarts, so just keep them in memory.
class LocalCache(AsyncCache):
    def __init__(self):
        self.cache = {}

    async def get(self, key: str):
        return self.cache.get(key)

    async def set(self, key: str, value, expires_in: int | None = None):
        # Ignore expiration in local mode.
        if value is not None:
            self.cache[key] = value
        else:
            self.cache.pop(key, None)

    async def delete(self, key: str):
        self.cache.pop(key, None)
