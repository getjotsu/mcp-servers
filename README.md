# mcp-servers
This is a collection of example MCP Servers for development.  See the individual README files for details.

## Servers

### hello
Basic server with a single tool.  Start here.

### oauth2
MCP server with full OAuth2 support.   Uses discord as a pass-through auth server.

## Client
There is a simple command line client `client/main.py` that each of the examples use.  
The client is just a thin wrapper around `mcp.streamable_client` and `jotsu-mcp` with `click` commands.
Other CLI clients don't seem to work well with streamable-http servers.

## References
* https://github.com/invariantlabs-ai/mcp-streamable-http
