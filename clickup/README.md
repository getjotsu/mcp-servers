# ClickUp - MCP Server

## setup
```shell
uv venv
source .venv/bin/activate  # or window equivalent
uv pip install .
```

* Create an API Key in your Clickup account.
* Create a file called `client.toml` with the bellow content.

```shell
[headers]
Authorization="Bearer [CLICKUP_API_KEY]"
```
where '[CLICKUP_API_KEY]' is replaced with the API Key you created (without brackets).


## server
```shell
python3 src/main.py
```

## client

List tools:
```shell
python3 ../client.py list-tools
```

List all of your workspaces/teams:
```shell
python3 ../client.py call-tool get_workspaces
```

Or against the deployed version:
```shell
python3 ../client.py --url=https://clickup.mcp.jotsu.com/mcp/ call-tool get_workspaces
```

## License
This server was based on ClickUp MCP Server by David Whatley and other contributors:

https://github.com/nsxdavid/clickup-mcp-server

Copyright (c) 2025 David Whatley and ClickUp MCP Server Contributors

Changes:
* Rewritten in Python.
* Added get_custom_fields tool.
* Add the ability to set custom fields in the create_task tool.

