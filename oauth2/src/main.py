import argparse
import logging
import os
from typing import MutableMapping

import httpx
from dotenv import load_dotenv

load_dotenv()

from local import LocalClientManager, LocalCache  # noqa
from server import make_server  # noqa

logger = logging.getLogger('oauth2')

mcp = make_server(
    client_manager=LocalClientManager(),
    cache=LocalCache(),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-level', default='WARNING')
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    mcp.run(transport='streamable-http')


if __name__ == '__main__':
    main()
