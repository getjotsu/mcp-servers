import json
import logging
import os
import time
import typing

import httpx
from pydantic import BaseModel, AnyHttpUrl
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.applications import Starlette

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse, HTMLResponse
from starlette.exceptions import HTTPException

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.auth.provider import OAuthAuthorizationServerProvider, AuthorizationParams, AuthorizationCode, \
    RefreshToken, AccessToken
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
import jwt

from jotsu.mcp.client import OAuth2AuthorizationCodeClient
from jotsu.mcp.client.utils import server_url

from clients import ClientManager
from cache import AsyncCache

T = typing.TypeVar('T', bound=BaseModel)

logger = logging.getLogger('oauth2-discord')


def get_redirect_uri(*, url: str, code: str | None, state: str):
    url = f'{url}?state={state}'
    if code:
        url += f'&code={code}'
    return url


# Get as a pydantic type.
async def cache_get(cache: AsyncCache, key: str, cls: typing.Type[T]) -> T | None:
    value = await cache.get(key)
    if value:
        return cls(**json.loads(value))
    return None


async def cache_set(cache: AsyncCache, key: str, value: BaseModel, expires_in: int | None = None) -> None:
    await cache.set(key, value=value.model_dump_json(), expires_in=expires_in)


class AuthServerProvider(OAuthAuthorizationServerProvider):
    # NOTE: these methods are declared in the order they are called.  See comments in parent class.
    def __init__(
            self, *,
            issuer_url: str,
            client_manager: ClientManager,
            cache: AsyncCache,
            oauth: OAuth2AuthorizationCodeClient, secret_key: str
    ):
        self.issuer_url = issuer_url  # only needed for the intermediate redirect.
        self.client_manager = client_manager
        self.cache = cache
        self.oauth = oauth
        self.secret_key = secret_key
        super().__init__()

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        logger.info('Registering client ... %s', client_info.model_dump_json())
        try:
            await self.client_manager.save_client(client_info)
            logger.info('Registered client: %s', client_info.client_id)
        except Exception as e:  # noqa
            logger.exception('Client registration failed.')

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return await self.client_manager.get_client(client_id)

    async def authorize(
            self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:

        # our redirect_uri
        assert params.redirect_uri in client.redirect_uris  # do better
        redirect_uri = server_url('/redirect', url=self.issuer_url)

        # If the client passed us a state value, use it, otherwise use authlib to generate one.
        params.state = params.state if params.state else self.oauth.generate_state()
        await cache_set(self.cache, params.state, params)

        logger.info(
            'authorize: %s, redirect_uri=%s, state=%s', params.model_dump_json(), redirect_uri, params.state
        )

        auth_info = await self.oauth.authorize_info(redirect_uri=redirect_uri, state=params.state)
        logger.info('authorize -> %s', auth_info.url)
        return auth_info.url

    # In between these calls, discord redirects back to our custom redirect.

    async def load_authorization_code(
            self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode:
        """OAuth2 flow, step 2: exchange the authorization code for access token
        """
        logger.info('load_authorization_code: %s %s', authorization_code, client.model_dump_json())
        params = await cache_get(self.cache, authorization_code, AuthorizationParams)

        # This is the last use of the cached code.
        await self.cache.delete(authorization_code)

        return AuthorizationCode(
            code=authorization_code,
            scopes=client.scope.split(' ') if client.scope else [],
            expires_at=time.time() + 10 * 60,  # Default, let discord catch this value.
            client_id=client.client_id,
            redirect_uri=params.redirect_uri,  # base value, without params
            redirect_uri_provided_explicitly=True,
            code_challenge=params.code_challenge
        )

    async def exchange_authorization_code(
            self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        redirect_uri = server_url('/redirect', url=self.issuer_url)
        logger.info(
            'exchange_authorization_code: %s, redirect_uri=%s',
            authorization_code.model_dump_json(), redirect_uri
        )

        try:
            discord_token = await self.oauth.exchange_authorization_code(
                code=authorization_code.code, redirect_uri=redirect_uri
            )
            return self._discord_token_to_oauth_token(client, discord_token)
        except httpx.HTTPStatusError as e:
            logger.error('oauth error [%d]: %s', e.response.status_code, e.response.text)
            raise HTTPException(status_code=500, detail=e.response.text)
        except Exception as e:  # noqa
            logger.exception('oauth error')
            raise HTTPException(status_code=500, detail=str(e))

    async def load_refresh_token(
            self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        logger.info('load_refresh_token: %s', refresh_token)

        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=['HS256'])
        except jwt.exceptions.DecodeError as e:
            logger.info('Invalid refresh JWT: %s', str(e))
            return None

        return RefreshToken(
            token=payload['token'],
            client_id=payload['client_id'],
            scopes=payload['scopes'],
            expires_at=payload['expires_at']
        )

    async def exchange_refresh_token(
            self,
            client: OAuthClientInformationFull,
            refresh_token: RefreshToken,
            scopes: list[str],
    ) -> OAuthToken | None:
        logger.info('exchange_refresh_token: %s', refresh_token.model_dump_json())
        discord_token = await self.oauth.exchange_refresh_token(refresh_token=refresh_token, scopes=scopes)
        return self._discord_token_to_oauth_token(client, discord_token) if discord_token else None

    async def load_access_token(self, token: str) -> AccessToken | None:
        logger.info('load_access_token: %s', token)

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
        except jwt.exceptions.DecodeError as e:
            logger.info('Invalid access JWT: %s', str(e))
            return None

        return AccessToken(
            token=payload['token'],
            client_id=payload['client_id'],
            scopes=payload['scopes'],
            expires_at=payload['expires_at']
        )

    async def revoke_token(
            self,
            token: AccessToken | RefreshToken,
    ) -> None:
        logger.info('revoke_token: %s', token)
        ...

    def _generate_jwt(self, token: AccessToken | RefreshToken) -> str:
        payload = {
            **token.model_dump(),
            'exp': token.expires_at,
            'iat': time.time(),
            'sub': token.client_id
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')

    def _discord_token_to_oauth_token(
            self, client: OAuthClientInformationFull, discord_token: OAuthToken
    ) -> OAuthToken:
        logger.info('Discord token: %s', discord_token.model_dump_json())

        # Convert the simple string tokens returned by Discord to JWTs.
        # This gives us the information we need later in load_access_token()/load_refresh_token()
        access_token = self._generate_jwt(
            AccessToken(
                token=discord_token.access_token,
                expires_at=int(time.time() + discord_token.expires_in),
                client_id=client.client_id,
                scopes=[client.scope] if client.scope else []
            )
        )
        refresh_token = self._generate_jwt(
            RefreshToken(
                token=discord_token.refresh_token,
                expires_at=int(time.time() + discord_token.expires_in),
                client_id=client.client_id,
                scopes=[client.scope] if client.scope else []
            )
        )

        logger.info('access_token: %s, expires_in=%s', access_token, discord_token.expires_in)

        return OAuthToken(
            access_token=access_token,
            expires_in=discord_token.expires_in,
            scope=client.scope,
            refresh_token=refresh_token
        )



class MCPServer(FastMCP):

    def __init__(
            self, *,
            client_manager: ClientManager,
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

        auth_server_provider = AuthServerProvider(
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
            stateless_http=True
        )

    def streamable_http_app(self) -> Starlette:
        app = super().streamable_http_app()
        app.add_middleware(HeadersMiddleware)  # type: ignore
        return app

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
        client_manager: ClientManager,
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

        logger.info('redirect: %s', str(request.query_params))
        params = await cache_get(mcp.cache, request.query_params['state'], AuthorizationParams)
        await cache.delete(request.query_params['state'])
        await cache_set(mcp.cache, request.query_params['code'], params)

        url = get_redirect_uri(url=str(params.redirect_uri), code=request.query_params.get('code'), state=params.state)
        return RedirectResponse(url=url)

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
        """
        return HTMLResponse(content=html)

    return mcp

