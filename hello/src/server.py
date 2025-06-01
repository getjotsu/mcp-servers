from starlette.responses import PlainTextResponse
from mcp.server.fastmcp import FastMCP


def setup_server(url: str = 'http://localhost:8000'):
    mcp = FastMCP('Hello MCP Server', stateless_http=True)

    # Basic dynamic resource returning a string
    @mcp.resource('resource://greeting')
    def get_greeting() -> str:
        """Provides a simple greeting message."""
        return f'Hello from {url}'

    # Resource returning JSON data (dict is auto-serialized)
    @mcp.resource('data://config', mime_type='application/json')
    def get_config() -> dict:
        """Provides example application configuration as JSON."""
        return {
            'theme': 'dark',
            'version': '1.2.0',
            'features': ['tools', 'resources'],
        }

    @mcp.tool()
    def greet(name: str) -> str:
        return f'Hello, {name}!'

    @mcp.custom_route('/', methods=['GET'])
    async def root(*_args):
        return PlainTextResponse('Hello World\n')

    return mcp
