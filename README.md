# mcp-servers
This is a collection of example MCP Servers for development.  See the individual README files for details.

## Servers

### hello
Basic server with a single tool.  Start here.

### oauth2
MCP server with full OAuth2 support.   Uses Discord as a pass-through auth server.

### discord
MCP server that can send messages to an authorized Discord server.   Uses a Discord Bot token for authorization.

### weather
The NWS Weather MCP server from the `modelcontextprotocol.io` adapted for deploying on Cloudflare.

NOTE: This server relies on the NWS API and may hit rate limits.

### mailgun
Send emails using [Mailgun](https://www.mailgun.com/).


## Client
There is a simple command line client `client.py` that each of the examples use.  
The client is just a thin wrapper around `mcp.streamable_client` and `jotsu-mcp` with `click` commands.
Other CLI clients don't seem to work well with streamable-http servers.

## References
* https://github.com/invariantlabs-ai/mcp-streamable-http
