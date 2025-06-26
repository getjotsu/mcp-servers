import logging
import os

import httpx
from jotsu.mcp.server import ThirdPartyAuthServerProvider, AsyncClientManager, AsyncCache, redirect_route
from pydantic import AnyHttpUrl

from starlette.requests import Request
from starlette.responses import Response, HTMLResponse
from starlette.exceptions import HTTPException

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
import jwt

from jotsu.mcp.client import OAuth2AuthorizationCodeClient

logger = logging.getLogger('oauth2-discord')


class MCPServer(FastMCP):

    def __init__(
            self, *,
            client_manager: AsyncClientManager,
            cache: AsyncCache,
            issuer_url: str | None = None
    ):
        issuer_url = issuer_url if issuer_url else 'http://localhost:8000/'
        logger.info('MCP Server: %s', issuer_url)

        self.client_manager = client_manager
        self.cache = cache

        self.oauth = OAuth2AuthorizationCodeClient(
            authorize_endpoint='https://discord.com/api/v10/oauth2/authorize',
            token_endpoint='https://discord.com/api/v10/oauth2/token',
            scope='identify',
            client_id=os.environ['DISCORD_CLIENT_ID'],
            client_secret=os.environ['DISCORD_CLIENT_SECRET']
        )

        # If a persistent key is not used, JWTs will only work until the server is restarted.
        self._secret_key = os.environ['SECRET_KEY']

        auth_server_provider = ThirdPartyAuthServerProvider(
            issuer_url=issuer_url,
            client_manager=self.client_manager,
            cache=self.cache,
            oauth=self.oauth,
            secret_key=self._secret_key
        )
        super().__init__(
            auth_server_provider=auth_server_provider,
            auth=AuthSettings(
                issuer_url=AnyHttpUrl(issuer_url),
                client_registration_options=ClientRegistrationOptions(enabled=True)
            ),
            stateless_http=True,
            json_response=True
        )

    def decode_jwt(self, token: str | None):
        """ Helper function for the whoami route."""
        if token:
            try:
                payload = jwt.decode(token, self._secret_key, algorithms=['HS256'])
                return payload['token']
            except jwt.exceptions.DecodeError as e:
                logger.info('Invalid refresh JWT: %s', str(e))

        return None


def make_server(
        *,
        client_manager: AsyncClientManager,
        cache: AsyncCache,
        issuer_url: str | None = None
):
    mcp = MCPServer(client_manager=client_manager, cache=cache, issuer_url=issuer_url)

    # See: https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization#2-2-example%3A-authorization-code-grant  # noqa
    # Handles 'Redirect to callback URL with auth code'
    # We add a custom route so that the same redirect can always be used in the discord oauth2 setup,
    # regardless of client.
    @mcp.custom_route('/redirect', methods=['GET'])
    async def redirect(request: Request) -> Response:
        """ This is the route that discord redirects back to on the MCP Server after authorization is complete. """
        return await redirect_route(request, cache=mcp.cache)

    @mcp.tool()
    async def whoami(ctx: Context) -> dict:
        """Returns information about the currently authenticated user."""
        authorization = ctx.request_context.request.headers.get('authorization')
        logger.info('[whoami] <- %s', authorization)

        headers = {}
        if authorization:
            _, token = authorization.split(' ', 1)
            bearer = mcp.decode_jwt(token)
            headers['Authorization'] = f'Bearer {bearer}'
            logger.info('[whoami] -> %s', headers['Authorization'])

        url = 'https://discord.com/api/v10/users/@me'
        try:
            async with httpx.AsyncClient() as httpx_client:
                logger.error(repr(httpx_client.get))
                res = await httpx_client.get(url, headers=headers)
                res.raise_for_status()
                logger.info('User data found: %s', res.text)
                return res.json()
        except httpx.HTTPStatusError as e:
            logger.error('%s [%d] -> %s', url, e.response.status_code, e.response.text)
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:  # noqa
            logger.exception('httpx.get: %s', str(e))
            raise e

    @mcp.custom_route('/', methods=['GET'])
    async def home() -> Response:
        """ Generic home route """
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>oauth2_discord</title>
        </head>
        <body>
            <h1>oauth2_discord</h1>
            <p>This is an example MCP server.  See <a href="https://github.com/getjotsu/mcp-servers/blob/main/oauth2/README.md">GitHub</a> for more details.
        </body>
        </html>
        """  # noqa
        return HTMLResponse(content=html)

    return mcp
