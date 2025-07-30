import httpx
from starlette.requests import Request


class MailgunClient(httpx.AsyncClient):

    BASE_URL = 'https://api.mailgun.net'

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    @classmethod
    def api_key(cls, request: Request):
        authorization = request.headers.get('Authorization')
        if authorization.lower().startswith('bearer '):
            return authorization[7:].strip()

        raise httpx.HTTPError('Missing or invalid Bearer token')

    def url(self, path: str):
        return f'{self.BASE_URL}{path}'
