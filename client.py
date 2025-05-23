import functools

import click
import asyncio
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

def async_cmd(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
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
    async with streamablehttp_client(url=ctx.obj['URL']) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


@click.group()
@click.option('--url', default='http://127.0.0.1:8000/mcp')
@click.pass_context
def cli(ctx, url):
    ctx.ensure_object(dict)
    ctx.obj['URL'] = url


@cli.command()
@click.pass_context
@async_cmd
async def list_tools(ctx):
    """List server tools"""
    async with client_session(ctx) as session:
        result = await session.list_tools()
        for tool in result.tools:
            click.echo(tool)


@cli.command()
@click.pass_context
@async_cmd
async def list_resources(ctx):
    """List server resources"""
    async with client_session(ctx) as session:
        result = await session.list_resources()
        for resource in result.resources:
            click.echo(resource)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.pass_context
@click.argument("name")
@click.argument("args", nargs=-1)
@async_cmd
async def call_tool(ctx, name, args):
    """Call/invoke a tool"""
    kwargs = click_kwargs(args)

    async with client_session(ctx) as session:
        result = await session.call_tool(name, kwargs)
        click.echo(result)


if __name__ == '__main__':
    cli()
