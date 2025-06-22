# weather - MCP Server

The `weather` example from `modelcontextprotocol.io` with added support for Cloudflare deployment.

The `weather.py` code from the documentation is found in `server.py`.


## Quick Start
Try this live at: https://weather.mcp.jotsu.com/mcp/.

e.g.
```
python3 ../client.py --url=https://weather.mcp.jotsu.com/mcp/ call-tool get_alerts --state=NY
```


## setup
```shell
uv venv
source .venv/bin/activate  # or window equivalent
uv pip install .
```

## server
```shell
python3 src/main.py
```

This is equivalent to (if `fastmcp` V2 is installed):
```shell
fastmcp run server.py --transport=streamable-http
```


## client

List tools:
```shell
python3 ../client.py list-tools
```

or list resources:
```shell
python3 ../client.py list-resources
```

## References
* https://modelcontextprotocol.io/quickstart/server
