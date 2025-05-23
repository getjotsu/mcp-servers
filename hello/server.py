from fastmcp import FastMCP

mcp = FastMCP('My MCP Server')

# Basic dynamic resource returning a string
@mcp.resource('resource://greeting')
def get_greeting() -> str:
    """Provides a simple greeting message."""
    return 'Hello from FastMCP Resources!'

# Resource returning JSON data (dict is auto-serialized)
@mcp.resource('data://config')
def get_config() -> dict:
    """Provides application configuration as JSON."""
    return {
        'theme': 'dark',
        'version': '1.2.0',
        'features': ['tools', 'resources'],
    }

@mcp.tool()
def greet(name: str) -> str:
    return f'Hello, {name}!'

if __name__ == '__main__':
    mcp.run(transport='streamable-http')
