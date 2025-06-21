import logging
import sys
import httpx_patch  # noqa: F401

sys.path.insert(0, '/session/metadata/vendor')
sys.path.insert(0, '/session/metadata')


logger = logging.getLogger(__name__)


async def on_fetch(request, env, ctx):
    # noinspection PyUnresolvedReferences
    import asgi
    from server import setup_server

    # Create two handlers - one for stdout and one for stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stderr_handler = logging.StreamHandler(sys.stderr)

    # Configure stdout handler to only handle INFO and DEBUG
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    # Configure stderr handler to only handle WARNING and above
    stderr_handler.setLevel(logging.WARNING)

    # Get the root logger and add both handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Allow all logs to pass through
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)

    mcp = setup_server()
    app = mcp.streamable_http_app()
    return await asgi.fetch(app, request, env, ctx)
