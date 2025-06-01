import base64
import json
import logging
import os
import sys
from unittest.mock import patch
from urllib.parse import urlparse, urlunparse, urlencode

sys.path.insert(0, '/session/metadata/vendor')
sys.path.insert(0, '/session/metadata')

import httpx

from mcp.shared.auth import OAuthClientInformationFull  # noqa: E402

from clients import ClientManager  # noqa: E402
from cache import AsyncCache  # noqa: E402

# Cloudflare automatic
from workers import fetch  # noqa


logger = logging.getLogger()


class KvClientManager(ClientManager):
    def __init__(self, env):
        self.env = env

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        value = await self.env.cache.get(client_id)
        return OAuthClientInformationFull(**json.loads(value)) if value else None

    async def save_client(self, client: OAuthClientInformationFull | None):
        await self.env.cache.put(client.client_id, client.model_dump_json())


class KvCache(AsyncCache):
    def __init__(self, env):
        self.env = env

    async def get(self, key: str):
        return await self.env.cache.get(key)

    async def set(self, key: str, value, expires_in: int | None = None):
        # FIXME: implement expiration in the case of failure.
        if value:
            await self.env.cache.put(key, value)
        else:
            await self.env.cache.delete(key)

    async def delete(self, key: str):
        await self.env.cache.delete(key)


def server_url(request) -> str:
    parsed = urlparse(request.url)
    parsed = parsed._replace(path='', query='', fragment='')
    return str(urlunparse(parsed))


class MockHttpxAsyncClient:
    async def get(self, url, **kwargs):
        logger.info('GET -> %s, kwargs=%s', url, str(kwargs))
        res = await fetch(str(url), method='GET', **kwargs)
        return await self._response(res, method='GET', url=url)

    @staticmethod
    def _btoa(text: str):
        return base64.b64encode(text.encode('latin1')).decode('ascii')

    async def post(self, url, **kwargs):
        headers = kwargs.pop('headers', {})

        if 'json' in kwargs:
            headers['Content-Type'] = 'application/json'
            kwargs['body'] = json.dumps(kwargs.pop('json'))
        elif 'data' in kwargs:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            kwargs['body'] = urlencode(kwargs.pop('data'))

        if 'auth' in kwargs:
            username, password = kwargs.pop('auth')
            basic_auth = self._btoa(f'{username}:{password}')
            headers['Authorization'] = f'Basic {basic_auth}'

        kwargs['headers'] = headers

        logger.info('POST -> %s, kwargs=%s', url, str(kwargs))
        res = await fetch(str(url), method='POST', **kwargs)
        return await self._response(res, method='POST', url=url)

    @staticmethod
    async def _response(res, *, method: str, url: str):
        req = httpx.Request(method=method, url=url)
        text = await res.text()

        json_data = None
        if res.status == 200:
            json_data = json.loads(text)

        logger.info('%s [%s] <- %s', method, res.status, text)
        return httpx.Response(res.status, text=text, json=json_data, request=req)


async def on_fetch(request, env, ctx):
    import asgi  # noqa
    from server import make_server

    logging.basicConfig(level='INFO')

    # Give the worker a normal environment.
    for key in ('DISCORD_CLIENT_ID', 'DISCORD_CLIENT_SECRET', 'SECRET_KEY'):
        os.environ[key] = getattr(env, key)

    httpx_client = MockHttpxAsyncClient()
    with patch.multiple('httpx.AsyncClient', get=httpx_client.get, post=httpx_client.post):
        mcp = make_server(
            issuer_url=server_url(request),
            client_manager=KvClientManager(env),
            cache=KvCache(env)
        )
        app = mcp.streamable_http_app()
        # app.add_exception_handler(HTTPException, http_exception)

        return await asgi.fetch(app, request, env, ctx)
