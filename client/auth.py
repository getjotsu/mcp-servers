import functools
import logging
import json
import threading
import urllib.parse
import webbrowser
from queue import Queue

import click
import httpx
import pkce
import pydantic
from mcp.server.auth.handlers.token import RefreshTokenRequest, AuthorizationCodeRequest

from client import utils, localserver

logger = logging.getLogger(__name__)


def get_access_token() -> str | None:
    credentials = utils.credentials_read()
    if credentials:
        return credentials.get('access_token')
    return None


def do_token_refresh() -> str | None:
    """ Try to use our refresh token to get a new access token. """
    credentials = utils.credentials_read()
    if credentials:
        refresh_token = credentials.get('refresh_token')
        token_endpoint = credentials.get('token_endpoint')

        if refresh_token and token_endpoint:
            req = RefreshTokenRequest(
                grant_type='refresh_token',
                refresh_token=refresh_token,
                scope=credentials.get('scope'),
                client_id=credentials.get('client_id'),
                client_secret=credentials.get('client_secret')
            )
            res = httpx.post(token_endpoint, data=req.model_dump())
            if res.status_code != 200:
                logger.info('Could not refresh access token: [%d] %s', res.status_code, res.text)
                return None

            # Keep values not included in the token response, like the endpoints.
            credentials = {**credentials, **res.json()}
            utils.credentials_save(credentials)
            return credentials['access_token']

    return None


def do_authentication(base_url: str) -> bool:
    # Try refresh first instead of forcing the user to re-authenticate.
    access_token = do_token_refresh()
    if access_token:
        # Credentials file is updated with a valid tokens, return and let the client read from there.
        return True

    # Server Metadata Discovery (SHOULD)
    url = utils.server_url('/.well-known/oauth-authorization-server', base_url=base_url)
    logger.info('Trying server metadata discovery at %s', url)
    try:
        res = httpx.get(url)
        server_metadata = res.json()
        authorization_endpoint = server_metadata['authorization_endpoint']
        token_endpoint = server_metadata['token_endpoint']
        registration_endpoint = server_metadata['registration_endpoint']
        logger.info('Server metadata found: %s', json.dumps(server_metadata))
    except httpx.HTTPStatusError as e:
        logger.info('Server metadata discovery not found, using default endpoints.', url)
        if e.response.status_code == 404:
            authorization_endpoint = utils.server_url('/authorize', base_url=base_url)
            token_endpoint = utils.server_url('/token', base_url=base_url)
            registration_endpoint = utils.server_url('/register', base_url=base_url)
        else:
            raise e

    # Dynamic Client Registration (SHOULD)
    # NOTE: fail if the server doesn't support DCR.
    logger.info('Trying dynamic client registration at %s', registration_endpoint)
    res = httpx.post(registration_endpoint, json={'redirect_uris': ['http://localhost:8001/']})
    res.raise_for_status()

    client = res.json()
    assert 'code' in client['response_types']
    logger.info('Client registration successful: %s', json.dumps(client))

    queue = Queue()
    httpd = localserver.LocalHTTPServer(queue)
    t = threading.Thread(target=httpd.serve_forever)
    t.daemon = True
    t.start()

    code_verifier, code_challenge = pkce.generate_pkce_pair()

    redirect_uri = urllib.parse.quote('http://localhost:8001/')
    url = f"{authorization_endpoint}?client_id={client['client_id']}" + \
        f'&response_type=code&code_challenge={code_challenge}&redirect_uri={redirect_uri}'
    click.echo(f'Opening a link in your default browser: {url}')
    webbrowser.open(url)

    # The local webserver writes an event to the queue on success.
    params = queue.get(timeout=120)
    logger.info('Browser authentication complete: %s', json.dumps(params))
    code = params.get('code')
    if not code:
        logger.error('Authorization failed, likely due to being canceled.')
        return False

    logger.info('Exchanging authorization code for token at %s', token_endpoint)

    req = AuthorizationCodeRequest(
        grant_type='authorization_code',
        code=code[0],
        code_verifier=code_verifier,
        client_id=client['client_id'],
        client_secret=client['client_secret'],
        redirect_uri=pydantic.AnyHttpUrl('http://localhost:8001/')
    )
    res = httpx.post(token_endpoint, data=req.model_dump(mode='json'))
    if res.status_code != 200:
        logger.warning('%d %s: %s', res.status_code, res.reason_phrase, res.text)
    res.raise_for_status()

    utils.credentials_save(
        res.json(),
        client_id=client['client_id'],
        client_secret=client['client_secret'],
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        registration_endpoint=registration_endpoint
    )
    return True


def authenticate(f):
    """
    Decorator for cli commands to automatically handle 401 responses from the server.
    This function must be called with @click.pass_context.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except BaseExceptionGroup as e:
            if not utils.is_httpx_401_exception(e):
                raise e

        ctx = args[0]
        base_url = ctx.obj['URL']
        if do_authentication(base_url=base_url):
            return f(*args, **kwargs)

        return None

    return wrapper
