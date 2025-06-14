import argparse
import logging
from dotenv import load_dotenv

load_dotenv()

from server import make_server  # noqa

logger = logging.getLogger('oauth2')

mcp = make_server()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-level', default='WARNING')
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level)
    mcp.run(transport='streamable-http')


if __name__ == '__main__':
    main()
