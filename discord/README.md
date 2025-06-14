# Discord - MCP Server
This server runs as a Bot application for your Discord Guild (i.e. server).

## Setup
You have to authorize the bot in Discord by doing:
* Create a discord application.
  * Go to https://discord.com/developers/applications and create a new application.
  * Click on 'Bot' on the left and click the 'Reset Token' button.   Copy the new token value when reset.
  * Enable all 'Privileged Gateway Intents' using the sliders:
    * Presence Intent
    * Server Members Intent
    * Message Content Intent
  * Follow the instructions https://discordjs.guide/preparations/adding-your-bot-to-servers.html to add the bot to your server.
    * Add at least the following permissions in the URL generator:
      * View Channels
      * View Server Insights
      * Send Messages
      * Send Messages in Threads


## Getting Started
Create a `client.toml` in the current directory (or your home directory) like:
```
[headers]
Authorization = "Bot <YOUR BOT TOKEN>"
```
using your Discord Bot token from above.

If everything is set up correctly, the server works locally:
```shell
python3 src/main.py
```

Then call it with a client.
```shell
python3 ../client.py call-tool get_server_info --server_id=<YOUR SERVER ID>
```


## References
This implementation is based on:
* https://github.com/hanweg/mcp-discord ([License](https://github.com/hanweg/mcp-discord/blob/main/LICENSE))


