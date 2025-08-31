from server import setup_server

mcp = setup_server()

if __name__ == '__main__':
    mcp.run(transport='streamable-http')
