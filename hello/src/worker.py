import logging
import sys
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, '/session/metadata/vendor')
sys.path.insert(0, '/session/metadata')

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response


logger = logging.getLogger(__name__)


async def http_exception(_request: Request, exc: Exception) -> Response:
    assert isinstance(exc, HTTPException)
    logger.exception(str(exc))
    if exc.status_code in {204, 304}:
        return Response(status_code=exc.status_code, headers=exc.headers)
    return PlainTextResponse(exc.detail, status_code=exc.status_code, headers=exc.headers)


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
    app.add_exception_handler(HTTPException, http_exception)
    return await asgi.fetch(app, request, env, ctx)
