# mcp-servers
This is a collection of example MCP Servers for development.  See the individual README files for details.

## Servers

### hello
Basic server with a single tool.  Start here.

## Client
There is a simple command line client `client.py` that each of the examples uses.  
The client is just a thin wrapper around `mcp.streamable_client` with `click` commands.
Other CLI clients don't seem to work well with streamable-http servers.

## References
* https://github.com/invariantlabs-ai/mcp-streamable-http
