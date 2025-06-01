import functools
import logging
import json
import threading
import urllib.parse
import webbrowser
from queue import Queue

import click
import pkce
from jotsu.mcp.client import OAuth2AuthorizationCodeClient
from mcp.server.auth.provider import RefreshToken

from client import utils, localserver

logger = logging.getLogger(__name__)


def get_access_token() -> str | None:
    credentials = utils.credentials_read()
    if credentials:
        return credentials.get('access_token')
    return None


async def token_refresh(credentials: dict) -> str | None:
    """ Try to use our refresh token to get a new access token. """
    oauth = OAuth2AuthorizationCodeClient(**credentials)

    refresh_token = RefreshToken(**credentials)
    token = await oauth.exchange_refresh_token(refresh_token=refresh_token, scopes=[])
    if token:
        # Keep values not included in the token response, like the endpoints.
        credentials = {**credentials, **token.model_dump(mode='json')}
        utils.credentials_save(credentials)
        return token.access_token
    return None


async def handle_authentication(mcp_url: str) -> bool:
    # Try refresh first instead of forcing the user to re-authenticate.
    credentials = utils.credentials_read()

    if credentials:
        access_token = token_refresh(credentials)
        if access_token:
            # Credentials file is updated with a valid tokens, return and let the client read from there.
            return True

    base_url = utils.server_url('', base_url=mcp_url)

    # Server Metadata Discovery (SHOULD)
    server_metadata = await OAuth2AuthorizationCodeClient.server_metadata_discovery(base_url=base_url)

    # Dynamic Client Registration (SHOULD)
    # NOTE: fail if the server doesn't support DCR.
    client_info = await OAuth2AuthorizationCodeClient.dynamic_client_registration(
        registration_endpoint=server_metadata.registration_endpoint, redirect_uris=['http://localhost:8001/']
    )

    queue = Queue()
    httpd = localserver.LocalHTTPServer(queue)
    t = threading.Thread(target=httpd.serve_forever)
    t.daemon = True
    t.start()

    code_verifier, code_challenge = pkce.generate_pkce_pair()

    redirect_uri = urllib.parse.quote('http://localhost:8001/')
    url = f"{server_metadata.authorization_endpoint}?client_id={client_info.client_id}" + \
        f'&response_type=code&code_challenge={code_challenge}&redirect_uri={redirect_uri}'
    click.echo(f'Opening a link in your default browser: {url}')
    webbrowser.open(url)

    # The local webserver writes an event to the queue on success.
    params = queue.get(timeout=120)
    logger.info('Browser authentication complete: %s', json.dumps(params))
    code = params.get('code')   # this is a list
    if not code:
        logger.error('Authorization failed, likely due to being canceled.')
        return False

    logger.info('Exchanging authorization code for token at %s', server_metadata.token_endpoint)

    client = OAuth2AuthorizationCodeClient(
        **client_info.model_dump(mode='json'),
        authorize_endpoint=server_metadata.authorization_endpoint,
        token_endpoint=server_metadata.token_endpoint
    )
    token = await client.exchange_authorization_code(
        code=code[0],
        code_verifier=code_verifier,
        redirect_uri='http://localhost:8001/'
    )

    utils.credentials_save(
        token.model_dump(mode='json'),
        client_id=client_info.client_id,
        client_secret=client_info.client_secret,
        authorization_endpoint=server_metadata.authorization_endpoint,
        token_endpoint=server_metadata.token_endpoint,
        registration_endpoint=server_metadata.registration_endpoint
    )
    return True


def authenticate(f):
    """
    Decorator for cli commands to automatically handle 401 responses from the server.
    This function must be called with @click.pass_context.
    """
    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except BaseExceptionGroup as e:
            if not utils.is_httpx_401_exception(e):
                raise e

        ctx = args[0]
        base_url = ctx.obj['URL']

        if await handle_authentication(mcp_url=base_url):
            return await f(*args, **kwargs)

        return None

    return wrapper
