# mailgun - MCP Server

## setup
```shell
uv venv
source .venv/bin/activate  # or window equivalent
uv pip install .
```

* Create an API Key in your Mailgun account.   Use 'developer' for the role.
* Create a file called `client.toml` with the bellow content.

```shell
[headers]
Authorization="Bearer [MAILGUN_API_KEY]"
```
where '[MAILGUN_API_KEY]' is replaced with the API Key you created (without brackets).


## server
```shell
python3 src/main.py
```

or to run (locally) as a Cloudflare worker:
```shell
npx wrangler dev --port 8000
```

## client

List tools:
```shell
python3 ../client.py list-tools
```

Call the one tool defined to send an email:
```shell
python3 ../client.py call-tool send_email --to='["recipient@example.com"]' --subject='Hello from MCP' --text='This is a sample text email.' --domain-name='mg.example.com'
```
Change the domain name to your Mailgun-specific domain-name (which likely begins with mg.).

Or against the deployed version:
```shell
python3 ../client.py --url=https://mailgun.mcp.jotsu.com/mcp/ call-tool send_email --to='["mattlaue@gmail.com"]' --subject='Hello from MCP' --text='This is a sample text email.' --domain-name='mg.jotsu.com'
```

## License
This server was based on the official MCP Server by Mailgun (which unfortunately only supports stdio as a transport).

https://github.com/mailgun/mailgun-mcp-server

Copyright 2025 Mailgun Technologies, Inc

http://www.apache.org/licenses/LICENSE-2.0

Changes:
* Rewritten in Python.

## References
* https://github.com/mailgun/mailgun-mcp-server
* https://github.com/danlapid/python-workers-mcp/blob/main/README.md
