import os
import logging
import asyncio
import websockets
from websockets import WebSocketClientProtocol
from Crypto.Cipher import ChaCha20

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ENV = os.environ
APP_KEY = ENV.get('APP_KEY')
APP_NONCE = ENV.get('APP_NONCE')
AUTH_TOKEN = ENV.get('AUTH_TOKEN', 'c571d2d4e914e5860a')

cipher = None
if APP_KEY and len(APP_KEY) == 32 and APP_NONCE and len(APP_NONCE) == 8:
    cipher = ChaCha20.new(key=APP_KEY.encode(), nonce=APP_NONCE.encode())
    logging.info(f"Using ChaCha20 encryption with key: {APP_KEY} and nonce: {APP_NONCE}")


def decrypt_message(message: bytes) -> bytes:
    if cipher:
        return cipher.decrypt(message)
    return message


def encrypt_message(message: bytes) -> bytes:
    if cipher:
        return cipher.encrypt(message)
    return message


def dict_to_query_string(params):
    return '&'.join([f'{key}={value}' for key, value in params.items()])


async def forwarder(reader, writer, websocket: WebSocketClientProtocol):
    async def send():
        while True:
            try:
                message = await websocket.recv()
                if isinstance(message, str):
                    message = message.encode()
                writer.write(decrypt_message(message))
                await writer.drain()
            except websockets.ConnectionClosed:
                writer.close()
                await writer.wait_closed()
                break

    async def recv():
        while True:
            data = await reader.read(100)
            if not data: break
            await websocket.send(data)
        # 关闭连接
        writer.close()
        await writer.wait_closed()
        await websocket.close()

    await asyncio.gather(send(), recv())


def parse_query_params(path):
    if '?' not in path:
        return {}
    query = path.split('?')[1]
    params = {}
    for param in query.split('&'):
        key, value = param.split('=')
        params[key] = value
    return params


class BindServer(object):
    def __init__(self, **kwargs):
        self.bind_host = kwargs.get('bind_host', ENV.get('BIND_HOST', '0.0.0.0'))
        self.bind_port = kwargs.get('bind_port', int(os.environ.get('BIND_PORT', '8765')))
        self.auth_token = kwargs.get('token', AUTH_TOKEN)
        self.default_host = kwargs.get('default_host', ENV.get('DEFAULT_HOST', '127.0.0.1'))
        self.default_port = kwargs.get('default_port', int(ENV.get('DEFAULT_PORT', '8080')))

    async def handle_client(self, websocket, path):
        params = parse_query_params(path)
        if params.get('token') != self.auth_token:
            await websocket.close(code=4001, reason="Authentication failed")
            return
        host = params.get('host', self.default_host)
        port = int(params.get('port', self.default_port))
        if not host or not port:
            await websocket.close(code=4002, reason="Invalid parameters")
            return
        reader, writer = await asyncio.open_connection(host, port)
        logging.info(f"Forwarding connection from {host}:{port}")
        await forwarder(reader, writer, websocket)

    async def run(self):
        server = await websockets.serve(self.handle_client, self.bind_host, self.bind_port)
        logging.info(f"WebSocket server started on ws://{self.bind_host}:{self.bind_port}")
        await server.wait_closed()


class ClientServer:
    def __init__(self, **kwargs):
        self.server_url = kwargs.get('server_url', ENV.get("SERVER_URL", "ws://127.0.0.1:8765"))
        self.auth_token = kwargs.get('auth_token', AUTH_TOKEN)
        self.local_host = kwargs.get('bind_host', '127.0.0.1')
        self.local_port = kwargs.get('bind_port', 1080)
        self.remote_host = kwargs.get('remote_host', '127.0.0.1')
        self.remote_port = kwargs.get('remote_port', 8088)
        self.max_client = kwargs.get('max_client', int(ENV.get('MAX_CLIENT', '100')))

    @property
    def ws_url(self):
        query_string = dict_to_query_string({
            'token': self.auth_token,
            'host': self.remote_host,
            'port': self.remote_port
        })
        return self.server_url + '?' + query_string

    async def handle_client(self, reader, writer):
        try:
            h, p = writer.get_extra_info('peername')
            addr = f"{h}:{p}"
            logging.info(f"Connection from {addr}")
            async with websockets.connect(self.ws_url) as websocket:
                await asyncio.create_task(forwarder(reader, writer, websocket))
        except ConnectionResetError:
            pass

    async def run(self):
        server = await asyncio.start_server(self.handle_client, self.local_host, self.local_port)
        host, port = server.sockets[0].getsockname()
        logging.info(f"Serving on tcp://{host}:{port}")
        async with server:
            await server.serve_forever()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='wsvpn: use websocket to forward tcp connection')
    parser.add_argument('type', choices=['client', 'server'], help='Specify the type: client or server')
    args = parser.parse_args()
    try:
        if args.type == 'server':
            b_server = BindServer()
            asyncio.run(b_server.run())
        elif args.type == 'client':
            c_server = ClientServer(
                server_url='ws://192.168.18.115:8765',
                remote_host='172.17.0.1',
                remote_port=22,
                bind_port=2222
            )
            asyncio.run(c_server.run())
    except KeyboardInterrupt:
        logging.info('Server closed')
    except Exception as e:
        logging.error(f"Error: {e}")
