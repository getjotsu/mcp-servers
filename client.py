import asyncio
import functools
import logging
import tomllib
import os.path
from contextlib import asynccontextmanager

import click
import httpx
import certifi

from jotsu.mcp.common.models import WorkflowServer
from jotsu.mcp.local import LocalMCPClient
from jotsu.mcp.client.utils import server_url

os.environ["SSL_CERT_FILE"] = certifi.where()
logger = logging.getLogger(__name__)

def async_cmd(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        coro = f(*args, **kwargs)
        if asyncio.iscoroutine(coro):
            return asyncio.run(coro)
        raise TypeError(f"Expected coroutine, got {type(coro)}")

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
            kwargs[key] = value
        else:
            raise click.UsageError(f'Unexpected argument: {arg}')
    return kwargs



@asynccontextmanager
async def client_session(ctx):
    server = WorkflowServer(id='server', name='server', url=ctx.obj['URL'])

    client = LocalMCPClient()
    async with client.session(server, headers=ctx.obj.get('headers')) as session:
        yield session


@click.group()
@click.option('--config', '-c', default=None)
@click.option('--url', default='http://127.0.0.1:8000/mcp/')
@click.option('--log-level', default='WARNING')
@click.pass_context
def cli(ctx, url, log_level, config):
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
    """List server resources"""
    async with client_session(ctx) as session:
        result = await session.read_resource(uri)
        for content in result.contents:
            click.echo(content)


@cli.command()
@click.pass_context
@async_cmd
async def list_tools(ctx):
    """List server tools"""
    async with client_session(ctx) as session:
        result = await session.list_tools()
        for tool in result.tools:
            click.echo(tool)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.pass_context
@click.argument('name')
@click.argument('args', nargs=-1)
@async_cmd
async def call_tool(ctx, name, args):
    """Call/invoke a tool"""
    kwargs = click_kwargs(args)
    async with client_session(ctx) as session:
        result = await session.call_tool(name, kwargs)
        click.echo(result)


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
