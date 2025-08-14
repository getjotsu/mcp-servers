from urllib.parse import quote_plus

import httpx
from starlette.requests import Request


class ClickupClient(httpx.AsyncClient):

    BASE_URL = 'https://api.clickup.com/api/v2'

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    @classmethod
    def api_key(cls, request: Request):
        authorization = request.headers.get('Authorization')
        if authorization.lower().startswith('bearer '):
            return authorization[7:].strip()

        raise httpx.HTTPError('Missing or invalid Bearer token')

    def url(self, path: str, params: dict = None):
        result = f'{self.BASE_URL}{path}'
        if params:
            args = []
            for key, value in params.items():
                if value is not None:
                    args.append(f'{key}={quote_plus(str(value))}')
            if args:
                result += '?' + '&'.join(args)
        return result

    @classmethod
    async def api_get(cls, request: Request, url: str, params: dict = None):
        api_key = cls.api_key(request)
        async with cls(api_key) as client:
            url = client.url(url, params)
            response = await client.get(url, headers={'Authorization': client.api_key})
            response.raise_for_status()
            return response.json()

    @classmethod
    async def api_post(cls, request: Request, url: str, data: dict = None):
        api_key = cls.api_key(request)
        async with cls(api_key) as client:
            url = client.url(url)
            response = await client.post(url, headers={'Authorization': client.api_key}, data=data)
            response.raise_for_status()
            return response.json()
