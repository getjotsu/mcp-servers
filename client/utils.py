import functools
import json
import typing
import os

import click
import asyncio
import httpx
from starlette.datastructures import URL


CLIENT_HOME = os.path.dirname(__file__)
HOME = os.path.dirname(CLIENT_HOME)
CREDENTIALS_PATH = os.path.join(HOME, 'credentials.json')


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


def is_httpx_401_exception(e: BaseExceptionGroup) -> bool:
    if e.exceptions and isinstance(e.exceptions[0], httpx.HTTPStatusError):
        status_error = typing.cast(httpx.HTTPStatusError, e.exceptions[0])
        if status_error.response.status_code == 401:
            return True
    return False


def server_url(path: str, *, base_url: str):
    if path.startswith('http://') or path.startswith('https://'):
        return path

    url = URL(base_url)
    return str(url.replace(path=path))


def mcp_url(path: str, *, base_url: str):
    if path.startswith('http://') or path.startswith('https://'):
        return path

    url = URL(base_url)
    return str(url.replace(path=url.path + path))


def credentials_save(credentials: dict, **kwargs) -> None:
    with open(CREDENTIALS_PATH, 'w') as fp:
        json.dump({**kwargs, **credentials}, fp, indent=4)


def credentials_read() -> dict | None:
    try:
        with open(CREDENTIALS_PATH, 'r') as fp:
            return json.load(fp)
    except (OSError, IOError):
        pass
    return None
