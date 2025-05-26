import typing
from http.server import HTTPServer, BaseHTTPRequestHandler
from queue import Queue
from urllib.parse import parse_qs


class RequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

        params = parse_qs(self.path[2:])  # path begins with /?

        # Write response body
        server: LocalHTTPServer = typing.cast(LocalHTTPServer, self.server)
        if params.get('code'):
            message = 'Authorization with Discord was successful.'
        else:
            message = 'Authorization with Discord did not complete :(.'

        message += ' You may close this tab and return to the client.'
        self.wfile.write(message.encode())

        server.queue.put(params)


class LocalHTTPServer(HTTPServer):

    def __init__(self, queue: Queue, port=8001):
        self.port = port
        self.queue = queue

        server_address = ('', port)
        super().__init__(server_address, RequestHandler)  # type: ignore


if __name__ == '__main__':
    httpd = LocalHTTPServer(Queue())
    httpd.serve_forever()
