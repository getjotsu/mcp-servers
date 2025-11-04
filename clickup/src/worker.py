import base64
import json
import logging
import sys
from urllib.parse import urlparse, urlunparse, urlencode

sys.path.insert(0, '/session/metadata/vendor')
sys.path.insert(0, '/session/metadata')

import httpx  # noqa

# Cloudflare automatic
from workers import fetch  # noqa


logger = logging.getLogger()


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

    logging.basicConfig(level='DEBUG')

    httpx_client = MockHttpxAsyncClient()
    httpx.AsyncClient.get = httpx_client.get
    httpx.AsyncClient.post = httpx_client.post

    mcp = make_server()
    app = mcp.streamable_http_app()

    return await asgi.fetch(app, request, env, ctx)
