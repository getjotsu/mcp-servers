import asyncio
import functools
import json
import logging
import tomllib
import os.path
from contextlib import asynccontextmanager

import click
import httpx
import certifi

from jotsu.mcp.types import WorkflowServer
from jotsu.mcp.local import LocalMCPClient
from jotsu.mcp.client.utils import server_url
from jotsu.mcp.types.shared import OAuthClientInformationFullWithBasicAuth

os.environ['SSL_CERT_FILE'] = certifi.where()
logger = logging.getLogger(__name__)

DEFAULT_PORT = 8000


def async_cmd(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        coro = f(*args, **kwargs)
        if asyncio.iscoroutine(coro):
            return asyncio.run(coro)
        raise TypeError(f'Expected coroutine, got {type(coro)}')

    return wrapper


def click_kwargs(args):
    kwargs = {}

    it = iter(args)
    for arg in it:
        if arg.startswith('--'):
            key = arg.lstrip('--')
            if '=' in key:
                key, value = key.split('=', 1)
            else:
                try:
                    value = next(it)
                except StopIteration:
                    raise click.UsageError(f'Missing value for {arg}')

            key = key.replace('-', '_')

            stripped = value.strip()
            if stripped.startswith('[') or stripped.startswith('{'):
                value = json.loads(value)

            kwargs[key] = value
        else:
            raise click.UsageError(f'Unexpected argument: {arg}')
    return kwargs


@asynccontextmanager
async def client_session(ctx):
    server = WorkflowServer(id='server', name='server', url=ctx.obj['URL'])

    headers = ctx.obj.get('headers')
    authenticate = ctx.obj.get('authenticate')

    client_id = ctx.obj.get('client_id')
    client_secret = ctx.obj.get('client_secret')

    if client_id and client_secret:
        server.client_info = OAuthClientInformationFullWithBasicAuth(
            client_id=client_id, client_secret=client_secret, redirect_uris=ctx.obj.get('redirect_uris')
        )

    client = LocalMCPClient()
    async with client.session(server, headers=headers, authenticate=authenticate) as session:
        yield session


@click.group()
@click.option('--config', '-c', default=None)
@click.option('--url', default=f'http://127.0.0.1:{DEFAULT_PORT}/mcp/')
@click.option('--log-level', default='WARNING')
@click.option('--authenticate', is_flag=True, default=False)
@click.option('--client-id', default=None)
@click.option('--client-secret', default=None)
@click.option('--redirect-uri', multiple=True)
@click.pass_context
def cli(ctx, url, log_level, authenticate, client_id, client_secret, config, redirect_uri):
    if not config:
        if os.path.exists('./client.toml'):
            config = './client.toml'
        elif os.path.exists('~/client.toml'):
            config = '~/client.toml'

    config_data = {}
    if config:
        with open(config, 'rb') as f:
            config_data = tomllib.load(f)

    logging.basicConfig(level=log_level)
    ctx.ensure_object(dict)

    ctx.obj['headers'] = httpx.Headers(config_data['headers']) if 'headers' in config_data else None
    ctx.obj['URL'] = url if url else config_data.get('URL')
    ctx.obj['client_id'] = client_id if client_id else config_data.get('client_id')
    ctx.obj['client_secret'] = client_secret if client_secret else config_data.get('client_secret')
    ctx.obj['redirect_uris'] = redirect_uri if redirect_uri else config_data.get('redirect_uris', [])
    ctx.obj['authenticate'] = authenticate if authenticate else config_data.get('authenticate')


@cli.command()
@click.pass_context
@async_cmd
async def list_resources(ctx):
    """List server resources"""
    async with client_session(ctx) as session:
        result = await session.list_resources()
        for resource in result.resources:
            click.echo(resource)


@cli.command()
@click.pass_context
@click.argument('uri')
@async_cmd
async def read_resource(ctx, uri):
    """Read a server resource by URI"""
    async with client_session(ctx) as session:
        result = await session.read_resource(uri)
        for content in result.contents:
            click.echo(content)


@cli.command()
@click.pass_context
@async_cmd
async def list_prompts(ctx):
    """List server prompts"""
    async with client_session(ctx) as session:
        result = await session.list_prompts()
        for resource in result.prompts:
            click.echo(resource)


@cli.command()
@click.pass_context
@click.argument('name')
@async_cmd
async def get_prompt(ctx, name):
    """Get a prompt by name"""
    async with client_session(ctx) as session:
        result = await session.get_prompt(name)
        for message in result.messages:
            click.echo(message)


@cli.command()
@click.pass_context
@click.option('--indent', type=int, default=None, help='The number of spaces to indent in JSON mode.')
@async_cmd
async def list_tools(ctx, indent: int):
    """List server tools"""

    async with client_session(ctx) as session:
        result = await session.list_tools()
        for tool in result.tools:
            click.echo(json.dumps(tool.model_dump(mode='json'), indent=indent))



@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.pass_context
@click.argument('name')
@click.option('--use-text', is_flag=True, help='Output as text.')
@click.option('--indent', type=int, default=None, help='The number of spaces to indent in JSON mode.')
@click.argument('args', nargs=-1)
@async_cmd
async def call_tool(ctx, name, args, use_text: bool, indent: int):
    """Call/invoke a tool"""
    kwargs = click_kwargs(args)
    async with client_session(ctx) as session:
        result = await session.call_tool(name, kwargs)

        if use_text:
            for content in result.content:
                if content.type == 'text':
                    click.echo(content.text)
        else:
            click.echo(json.dumps(result.model_dump(mode='json'), indent=indent))



@cli.command()
@click.argument('path')
@click.pass_context
def get(ctx, path: str):
    """Send a GET request to the server."""
    url = server_url(path, url=ctx.obj['URL'])
    res = httpx.get(url)
    res.raise_for_status()
    click.echo(res.text)


if __name__ == '__main__':
    cli()
