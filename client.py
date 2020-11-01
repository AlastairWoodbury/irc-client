import asyncio
import re

from enums import Response
from message import ServerMessage

__all__ = (
    'Client'
)

SERVER_MESSAGE_RE = re.compile(r':(?P<prefix>.+) (?P<code>\d{3}|\w{1,2}) (?P<user>\w+) :(?P<params>.+)')
MESSAGE_RE = re.compile(r':(?P<nick>.+)!(?P<username>.+)@(?P<host>.+) PRIVMSG (?P<channel>.+) :(?P<message>.+)')


class Client:
    def __init__(
        self,
        *,
        nick: str = None,
        username: str = None,
        password: str = None,
        loop: asyncio.AbstractEventLoop = None
    ) -> None:
        self.nick = nick
        self.username = username
        self.password = password
        self.loop = loop or asyncio.get_event_loop()

        self._waiters = {}

    async def connect(
        self,
        host: str,
        port: int = 6667,
        *,
        nick: str = ...,
        username: str = ...,
        password: str = ...
    ):
        if nick is ... and not self.nick:
            raise ValueError('No nickname set')

        if username is ... and not self.username:
            raise ValueError('No username set')

        if password is ... and not self.password:
            raise ValueError('No password set')

        self.reader, self.writer = await asyncio.open_connection(
            host,
            port
        )

        self._recieve_task = self.loop.create_task(
            self.recieve_loop()
        )

        password = password if password is not ... else self.password
        username = username if username is not ... else self.username
        nick = nick if nick is not ... else self.nick

        await self.set_nick(nick)
        await self.send_command('USER', args=f'{username} * *', params='turtle')

    async def recieve_loop(self) -> None:
        while True:
            data = await self.reader.readuntil(b'\r\n')
            print(f'< {data.decode().strip()}')
            self.loop.create_task(
                self.handle_recieve(data)
            )

    async def handle_recieve(self, data: bytes) -> None:
        data = data.decode()
        await self.dispatch('raw_socket_recieve', data)

    async def dispatch(self, event: str, *args, **kwargs) -> None:
        func = getattr(self, f'on_{event}')
        await func(*args, **kwargs)

    async def wait_for(self, code: Response, *, timeout: int = None) -> any:
        print('heck')

    async def send_command(self, command: str, *, args: str = None, params: str = None) -> None:
        args = f'{args.strip()} ' if args else ''
        params = f':{params.strip()}' if params else ''
        await self.send_raw(f'{command.strip()} {args}{params}\r\n'.encode())

    async def send_raw(self, data: bytes) -> None:
        print(f'> {data.decode().strip()}')
        self.writer.write(data)
        await self.writer.drain()

    async def on_raw_socket_recieve(self, message: str) -> None:
        if match := re.match(SERVER_MESSAGE_RE, message):  # Server message
            match_dict = match.groupdict()
            match_dict['code'] = int(match_dict['code'])
            message = ServerMessage(**match_dict)
            await self.dispatch('server_message', message)

        elif match := re.match(MESSAGE_RE, message):  # User message
            await self.dispatch('message', match['message'])

    async def on_server_message(self, message):
        print(f'+ {message}')

    async def on_message(self, message) -> None:
        print(f'~ {message}')

    async def close(self, reason: str = None) -> None:
        await self.send_command('QUIT', params=reason)
        self._recieve_task.cancel()
        self.writer.close()
        await self.writer.wait_closed()

    async def set_nick(self, new_nick: str) -> None:
        await self.send_command('NICK', args=new_nick)

    async def join_channel(self, name: str) -> None:
        await self.send_command('JOIN', args=name)

    async def send_message(self, channel: str, message: str) -> None:
        await self.send_command('PRIVMSG', args=channel, params=message)
