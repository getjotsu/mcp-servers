# hello - MCP Server

## setup
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
python3 ../client/main.py list-tools
```

Call the one tool defined:
```shell
python3 ../client/main.py call-tool greet --name='World'
```

or list resources:
```shell
python3 ../client/main.py list-resources
```

## References
* https://github.com/danlapid/python-workers-mcp/blob/main/README.md
