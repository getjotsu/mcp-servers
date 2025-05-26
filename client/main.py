import logging
import os
import sys

import click
import httpx
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client import utils  # noqa
from client.auth import authenticate, get_access_token  # noqa


logger = logging.getLogger(__name__)


@asynccontextmanager
async def client_session(ctx):
    headers = {}
    access_token = get_access_token()
    if access_token:
        headers['Authorization'] = f'Bearer {access_token}'

    async with streamablehttp_client(
        url=ctx.obj['URL'],
        headers=headers,
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


@click.group()
@click.option('--url', default='http://127.0.0.1:8000/mcp/')
@click.option('--log-level', default='WARNING')
@click.pass_context
def cli(ctx, url, log_level):
    logging.basicConfig(level=log_level)
    ctx.ensure_object(dict)
    ctx.obj['URL'] = url


@cli.command()
@click.pass_context
@authenticate
@utils.async_cmd
async def list_tools(ctx):
    """List server tools"""
    async with client_session(ctx) as session:
        result = await session.list_tools()
        for tool in result.tools:
            click.echo(tool)


@cli.command()
@click.pass_context
@authenticate
@utils.async_cmd
async def list_resources(ctx):
    """List server resources"""
    async with client_session(ctx) as session:
        result = await session.list_resources()
        for resource in result.resources:
            click.echo(resource)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.pass_context
@click.argument('name')
@click.argument('args', nargs=-1)
@authenticate
@utils.async_cmd
async def call_tool(ctx, name, args):
    """Call/invoke a tool"""
    kwargs = utils.click_kwargs(args)
    async with client_session(ctx) as session:
        result = await session.call_tool(name, kwargs)
        click.echo(result)


@cli.command()
@click.argument('path')
@click.pass_context
def get(ctx, path: str):
    """Send a GET request to the server."""
    url = utils.server_url(path, base_url=ctx.obj['URL'])
    res = httpx.get(url)
    res.raise_for_status()
    click.echo(res.text)


if __name__ == '__main__':
    cli()
