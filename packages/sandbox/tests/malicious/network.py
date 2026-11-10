import socket


def main(data):
    connection = socket.create_connection(("example.com", 80))
    return {"summary": str(connection)}
