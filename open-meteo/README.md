# open-meteo - MCP Server

Weather conditions from https://open-meteo.com/.

This code is from the Medium article
[Building Your First MCP Server: A Weather API Integration with Claude](https://medium.com/@rnwqyzxnn/building-your-first-mcp-server-a-weather-api-integration-with-claude-f21f19674717) by Oskar Ablimit.


The Medium article is a repackaging of the example from modelcontextprotocol.io, just using OpenMeteo instead of NWS.  
See the [weather](https://github.com/getjotsu/mcp-servers/tree/main/weather) example.


## Quick Start
Try this live at: https://open-meteo.mcp.jotsu.com/mcp/.

e.g.
```
python3 ../client.py --url=https://open-meteo.mcp.jotsu.com/mcp/ call-tool get_forecast --latitude=36.5785 --longitude=-118.2923 --use-text
```
(This is the summit of Mt Whitney in CA, US)


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

You can also run it as a local Cloudflare worker:
```shell
npx wrangler dev
```
NOTE: wrangler uses port 8787 instead of the default 8000.


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

## License
The Open-Meteo API is free for non-commercial use but requires a license for commercial applications.  
Learn more on [Open-Meteo](https://open-meteo.com/en/pricing) website.
