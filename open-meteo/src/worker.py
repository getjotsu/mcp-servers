import json
import logging
import sys

sys.path.insert(0, '/session/metadata/vendor')
sys.path.insert(0, '/session/metadata')

import httpx  # noqa: E402
# Cloudflare automatic
from workers import fetch  # noqa


logger = logging.getLogger(__name__)


# Early workers had problems with httpx (see httpx_patch in other examples)
# This patch is needed to reliably a) set the USER_AGENT header and b) force ipv4.
class MockHttpxAsyncClient:
    async def get(self, url, **kwargs):
        res = await fetch(str(url), method='GET', cf={'ipv6': False}, **kwargs)
        return await self._response(res, method='GET', url=url)

    # noinspection DuplicatedCode
    @staticmethod
    async def _response(res, *, method: str, url: str):
        req = httpx.Request(method=method, url=url)
        text = await res.text()

        json_data = None
        if res.status == 200:
            json_data = json.loads(text)

        return httpx.Response(res.status, text=text, json=json_data, request=req)


async def on_fetch(request, env, ctx):
    # noinspection PyUnresolvedReferences
    import asgi
    from server import setup_server

    # Create two handlers - one for stdout and one for stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stderr_handler = logging.StreamHandler(sys.stderr)

    # Configure stdout handler to only handle INFO and DEBUG
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    # Configure stderr handler to only handle WARNING and above
    stderr_handler.setLevel(logging.WARNING)

    # Get the root logger and add both handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Allow all logs to pass through
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)

    httpx_client = MockHttpxAsyncClient()
    httpx.AsyncClient.get = httpx_client.get

    mcp = setup_server()
    app = mcp.streamable_http_app()
    return await asgi.fetch(app, request, env, ctx)
