import logging

import httpx
from mcp.server.fastmcp import FastMCP, Context
from starlette.requests import Request
from starlette.responses import Response, HTMLResponse

from discord import DiscordClient

logger = logging.getLogger('discord')


class DiscordServer(FastMCP):

    @staticmethod
    def get_bot_token(request: Request):
        authorization = request.headers.get('Authorization')
        if authorization.lower().startswith('bot '):
            return authorization[4:].strip()

        raise httpx.HTTPError('Missing or invalid Bot token')


def make_server():
    mcp = DiscordServer(name='discord', stateless_http=True)

    @mcp.tool(description='Retrieve information about the server/guild referred to by the provided server ID.')
    async def get_server_info(ctx: Context, server_id: str):
        bot_token = mcp.get_bot_token(ctx.request_context.request)
        async with DiscordClient(bot_token) as client:
            return await client.get_server_info(server_id)

    @mcp.custom_route('/', methods=['GET'])
    async def home() -> Response:
        """ Generic home route """
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Discord MCP Server</title>
        </head>
        <body>
            <h1>Discord (unofficial)</h1>
            <p>See <a href="https://github.com/getjotsu/mcp-servers/blob/main/discord/README.md">GitHub</a> for more details.
        </body>
        </html>
        """  # noqa
        return HTMLResponse(content=html)

    return mcp
