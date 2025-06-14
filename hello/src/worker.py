import logging
import sys
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, '/session/metadata/vendor')
sys.path.insert(0, '/session/metadata')

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response


logger = logging.getLogger(__name__)


def server_url(request) -> str:
    parsed = urlparse(request.url)
    parsed = parsed._replace(path='')
    return str(urlunparse(parsed))


async def on_fetch(request, env, ctx):
    # noinspection PyUnresolvedReferences
    import asgi
    from server import setup_server

    mcp = setup_server(url=server_url(request))
    app = mcp.streamable_http_app()
    return await asgi.fetch(app, request, env, ctx)
