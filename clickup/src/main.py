from server import make_server

mcp = make_server()

if __name__ == '__main__':
    mcp.run(transport='streamable-http')
