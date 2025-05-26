import argparse
import asyncio
import json
import logging
import os
import secrets
import time
import typing
from types import SimpleNamespace

from authlib.integrations.starlette_client import OAuth, OAuthError
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.config import Config
from dotenv import load_dotenv

from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware

from fastmcp import FastMCP
from mcp.server.auth.provider import OAuthAuthorizationServerProvider, AuthorizationParams, AuthorizationCode, \
    RefreshToken, AccessToken
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
import jwt

logger = logging.getLogger(__name__)

load_dotenv()
HOME = os.path.dirname(os.path.dirname(__file__))
CLIENTS_FILE = os.path.join('clients.json')

# configure OAuth client
config = Config(environ={})  # you could also read the client ID and secret from a .env file
oauth = OAuth(config=config)
oauth.register(  # this allows us to call oauth.discord later on
    'discord',
    authorize_url='https://discord.com/api/oauth2/authorize',
    access_token_url='https://discord.com/api/oauth2/token',
    refresh_token_url='https://discord.com/api/oauth2/token',
    scope='identify',
    client_id=os.environ['DISCORD_CLIENT_ID'],
    client_secret=os.environ['DISCORD_CLIENT_SECRET']
)

# If a persistent key is not used, JWTs will only work until the server is restarted.
secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))


class MCPClient:
    clients: typing.Dict[str, typing.Self] = {}
    lock = asyncio.Lock()

    def __init__(self, client_info: OAuthClientInformationFull):
        self.client_info = client_info

        # This replaces request.session of Starlette requests
        # that we don't have access to in OAuthAuthorizationServerProvider
        self.session = {}

        # There is one state and code shared between us and discord.
        self.state = ''

        self.params: AuthorizationParams | None = None

    def redirect_uri(self, *, code: str | None, state: str):
        url = f'{str(self.params.redirect_uri)}?state={state}'
        if code:
            url += f'&code={code}'
        return url

    @classmethod
    def get_by_state(cls, state: str) -> typing.Self | None:
        for client in cls.clients.values():
            if client.state == state:
                return client
        return None

    @classmethod
    async def save_clients(cls):
        """
        Clients have to persist across server restarts, so save them in a simple JSON file in the root directory.
        """
        async with cls.lock:
            try:
                with open(CLIENTS_FILE, 'w') as fp:
                    obj = [client.client_info.model_dump(mode='json') for client in cls.clients.values()]
                    json.dump(obj, fp=fp)
            except OSError:
                pass

    @classmethod
    def load_clients(cls):
        """ Only called on server startup so we don't need to lock."""
        try:
            with open(CLIENTS_FILE, 'r') as fp:
                obj = json.load(fp)
                cls.clients = {
                    client_info['client_id']: MCPClient(OAuthClientInformationFull(**client_info))
                    for client_info in obj
                }
        except (OSError, json.JSONDecodeError):
            pass


class AuthServerProvider(OAuthAuthorizationServerProvider):
    # NOTE: these methods are declared in the order they are called.  See comments in parent class.

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        MCPClient.clients[client_info.client_id] = MCPClient(client_info)
        await MCPClient.save_clients()
        logger.info('Registered client: %s', client_info.model_dump_json())

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        client = MCPClient.clients.get(client_id)
        return client.client_info if client else None

    async def authorize(
            self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        # We don't have the actual request session
        mcp_client = MCPClient.clients[client.client_id]
        mcp_client.params = params

        # our redirect_uri
        assert params.redirect_uri in mcp_client.client_info.redirect_uris  # do better
        redirect_uri = 'http://localhost:8000/redirect'

        # If the client passed us a state value, use it, otherwise authlib will generate one.
        state = params.state

        # res: RedirectResponse = await oauth.discord.authorize_redirect(request, redirect_uri=redirect_uri)
        rv = await oauth.discord.create_authorization_url(redirect_uri, state=state)
        rv['redirect_uri'] = redirect_uri
        mcp_client.state = rv.pop('state', None)
        await oauth.discord.framework.set_state_data(mcp_client.session, mcp_client.state, rv)

        logger.info('authorize: %s -> %s, state=%s', params.model_dump_json(), rv['url'], mcp_client.state)
        return rv['url']

    async def load_authorization_code(
            self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode:
        """OAuth2 flow, step 2: exchange the authorization code for access token
        """
        mcp_client = MCPClient.clients[client.client_id]
        logger.info('load_authorization_code: %s %s', authorization_code, client.model_dump_json())

        return AuthorizationCode(
            code=authorization_code,
            scopes=[mcp_client.client_info.scope] if mcp_client.client_info.scope else [],
            expires_at=time.time() + 10 * 60,  # Default, let discord catch this value.
            client_id=mcp_client.client_info.client_id,
            redirect_uri=mcp_client.params.redirect_uri,  # base value, without params
            redirect_uri_provided_explicitly=True,
            code_challenge=mcp_client.params.code_challenge
        )

    async def exchange_authorization_code(
            self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        mcp_client = MCPClient.clients[client.client_id]
        logger.info('exchange_authorization_code: %s', authorization_code.model_dump_json())

        # exchange auth code for token
        try:
            request = SimpleNamespace()
            request.session = mcp_client.session
            request.query_params = {
                'code': authorization_code.code,
                'state': mcp_client.state
            }
            discord_token = await oauth.discord.authorize_access_token(request)
        except OAuthError as error:
            logger.error('OAuthError 500: %s', error.error)
            raise HTTPException(status_code=500, detail=error.error)

        return self._discord_token_to_oauth_token(client, discord_token)

    async def load_refresh_token(
            self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        logger.info('load_refresh_token: %s', refresh_token)

        try:
            payload = jwt.decode(refresh_token, secret_key, algorithms=['HS256'])
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
        try:
            discord_token = await oauth.discord.fetch_access_token()
        except OAuthError as error:
            logger.warning('Failed to exchange refresh token: %s', error.error)
            return None

        discord_token['refresh_token'] = refresh_token.token
        return self._discord_token_to_oauth_token(client, discord_token)

    async def load_access_token(self, token: str) -> AccessToken | None:
        logger.info('load_access_token: %s', token)

        try:
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
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

    @staticmethod
    def _generate_jwt(token: AccessToken | RefreshToken) -> str:
        payload = {
            **token.model_dump(),
            'exp': token.expires_at,
            'iat': time.time(),
            'sub': token.client_id
        }
        return jwt.encode(payload, secret_key, algorithm='HS256')

    def _discord_token_to_oauth_token(self, client: OAuthClientInformationFull, discord_token: dict) -> OAuthToken:
        logger.info('Discord token: %s', json.dumps(discord_token))
        discord_token['token_type'] = discord_token['token_type'].lower()

        # Convert the simple string tokens returned by Discord to JWTs.
        # This gives us the information we need later in load_access_token()/load_refresh_token()
        access_token = self._generate_jwt(
            AccessToken(
                token=discord_token['access_token'],
                expires_at=int(time.time() + discord_token['expires_in']),
                client_id=client.client_id,
                scopes=[client.scope] if client.scope else []
            )
        )
        refresh_token = self._generate_jwt(
            RefreshToken(
                token=discord_token['refresh_token'],
                expires_at=int(time.time() + discord_token['expires_in']),
                client_id=client.client_id,
                scopes=[client.scope] if client.scope else []
            )
        )

        return OAuthToken(
            access_token=access_token,
            expires_in=discord_token['expires_in'],
            scope=client.scope,
            refresh_token=refresh_token
        )


class MCPServer(FastMCP):
    def __init__(self):
        MCPClient.load_clients()
        super().__init__(
            auth_server_provider=AuthServerProvider(),
            auth=AuthSettings(
                issuer_url='http://localhost:8000/',  # type: ignore
                client_registration_options=ClientRegistrationOptions(enabled=True)
            ),
        )

    def http_app(
            self,
            path: str | None = None,
            middleware: list[Middleware] | None = None,
            transport: typing.Literal['streamable-http', 'sse'] = 'streamable-http',
    ):
        middleware = middleware if middleware else []

        # FIXME: remove
        middleware.append(Middleware(SessionMiddleware, secret_key=secret_key))  # type: ignore
        return super().http_app(path, middleware, transport)


mcp = MCPServer()


# See: https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization#2-2-example%3A-authorization-code-grant  # noqa
# Handles 'Redirect to callback URL with auth code'
# We add a custom route so that the same redirect can always be used in the discord oauth2 setup, regardless of client.
@mcp.custom_route('/redirect', methods=['GET'])
async def redirect(request: Request) -> Response:
    """ This is the route that discord redirects back to on the MCP Server after authorization is complete. """
    logger.info('redirect: %s', str(request.query_params))
    state = request.query_params['state']
    mcp_client = MCPClient.get_by_state(state)

    # This discord code is reused, but the state is replaced with the one from this server.
    url = mcp_client.redirect_uri(code=request.query_params.get('code'), state=mcp_client.state)
    return RedirectResponse(url=url)


@mcp.tool()
def protected() -> str:
    return 'Hello World!'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-level', default='WARNING')
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    mcp.run(transport='streamable-http')


if __name__ == '__main__':
    main()
