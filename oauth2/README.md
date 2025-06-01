# OAuth2 - MCP Server
This server has 'protected' tools.

## Prerequisites
This example uses a Discord application as the authentication provider so you have to:
* Create a discord application.
  * Go to https://discord.com/developers/applications and create a new application.
  * Click on OAuth2 in the side navigation and copy the Client ID and Client Secret (you may have to regenerate).
* Authorize the redirect uri.
  * Click on Redirects in the sidebar and add 'http://localhost:8000/redirect'

## Setup
Create a `.env` file in this directory with the following:
```shell
DISCORD_CLIENT_ID=<DISCORD_CLIENT_ID>
DISCORD_CLIENT_SECRET=<DISCORD_CLIENT_SECRET>
SECRET_KEY=<random value>
```
replacing the values with the client ID and client secret from your Discord application above.

The secret key should be a random value.  A good way to generate a secret is:
```shell
python3 -c 'import secrets;print(secrets.token_hex(16))'
```

```shell
uv venv
source .venv/bin/activate  # or window equivalent
uv pip install .
```

## server
```shell
fastmcp run server.py --transport=streamable-http
```

## client

List tools:
```shell
python3 ../client/main.py call-tool protected
```

## Overview
The server supports the OAuth 2.1 flow for the authorization code grant type.  
See https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization#2-2-example%3A-authorization-code-grant

Discord acts as the auth provider for this example server.

### Server Metadata Discovery
When the client tries to interact with the server it initially gets a '401 Unauthorized' response.
On seeing the 401, the client starts the OAuth flow by first discovering server authorization metadata.

The client sends a GET request to `/.well-known/oauth-authorization-server` on the MCP server domain.

```shell
python3 ../client.py get /.well-known/oauth-authorization-server
```

## Cloudflare

### KV
This client uses a single Cloudflare KV store for both cache and clients.

```shell
npx wrangler kv namespace create cache
```

and replace the "id" of "cache" in the "kv_namespaces" section of `wrangler.jsonc`.

### Worker environment
The worker need additional packages beyond the standard library.  To build the pyodide environment:
```shell
make
```

Try it locally:
```shell
npx wrangler dev
```

Make sure you've added your environment to `.dev.vars`.

To deploy it, you'll need to set the values as secrets via wrangler:
```shell
npx wrangler secret put DISCORD_CLIENT_ID
npx wrangler secret put DISCORD_CLIENT_SECRET
npx wrangler secret put SECRET_KEY
```

## References
* https://github.com/lukasthaler/fastapi-oauth-examples
