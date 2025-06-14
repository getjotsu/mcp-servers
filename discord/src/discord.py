import httpx


class DiscordClient(httpx.AsyncClient):

    BASE_URL = 'https://discord.com/api'

    def __init__(self, bot_token: str):
        super().__init__()
        self.bot_token = bot_token

    async def get_server_info(self, server_id: str):
        url = f'{self.BASE_URL}/guilds/{server_id}'

        headers = {
            'Authorization': f'Bot {self.bot_token}'
        }

        response = await self.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def send_message(self, channel_id: str, content: str) -> None:
        url = f'{self.BASE_URL}/channels/{channel_id}/messages'
        headers = {
            'Authorization': f'Bot {self.bot_token}',
            'Content-Type': 'application/json'
        }
        json = {'content': content}

        response = httpx.post(url, headers=headers, json=json)
        response.raise_for_status()
