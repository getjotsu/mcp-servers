import base64
import typing

import pydantic
from mcp.server.fastmcp import FastMCP, Context

DEFAULT_PORT = 8000


class InlineAttachment(pydantic.BaseModel):
    filename: str
    content_type: typing.Optional[str] = 'application/octet-stream'
    data_base64: str  # base64-encoded image content


class SendEmailResponse(pydantic.BaseModel):
    id: str
    message: str


def setup_server():
    from mailgun import MailgunClient

    mcp = FastMCP('Mailgun MCP Server', stateless_http=True, json_response=True, port=DEFAULT_PORT)

    @mcp.tool()
    async def send_email(
            ctx: Context,
            domain_name: typing.Annotated[str, 'Domain name used to send the message'],
            to: typing.List[str],
            subject: str,
            cc: typing.Optional[typing.List[str]] = None,
            bcc: typing.Optional[typing.List[str]] = None,
            sender: typing.Optional[str] = None,
            text: typing.Annotated[typing.Optional[str], 'Body of the message (text version)'] = None,
            html: typing.Annotated[typing.Optional[str], 'Body of the message (HTML version)'] = None,
            inline_attachments: typing.Optional[typing.List[InlineAttachment]] = None
    ) -> SendEmailResponse:
        """Pass the components of the messages such as To, From, Subject, HTML and
        text parts, attachments, etc. Mailgun will build a MIME representation
        of the message and send it. Note: In order to send you must provide one
        of the following parameters: 'text', 'html', 'amp-html' or 'template'."""

        sender = sender or f'Mailgun MCP <mailgun@{domain_name}>'
        data = {
            'from': sender,
            'to': to,
            'subject': subject,
        }

        if text is not None:
            data['text'] = text
        if html is not None:
            data['html'] = html
        if cc is not None:
            data['cc'] = cc
        if bcc is not None:
            data['bcc'] = cc

        files = []
        if inline_attachments:
            for a in inline_attachments:
                raw_bytes = base64.b64decode(a.data_base64)
                files.append((
                    'inline',
                    (a.filename, raw_bytes, a.content_type)
                ))

        api_key = MailgunClient.api_key(ctx.request_context.request)
        async with MailgunClient(api_key) as client:
            url = client.url(f'/v3/{domain_name}/messages')
            response = await client.post(
                url,
                auth=('api', api_key),
                data=data,
                files=files or None
            )

            if response.status_code != 200:
                raise RuntimeError(f'Mailgun error {response.status_code}: {response.text}')

        return SendEmailResponse(**response.json())

    return mcp
