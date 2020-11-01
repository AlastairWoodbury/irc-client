import asyncio
import logging
import re
from typing import Callable

from enums import Response
from message import Message, ServerMessage

__all__ = (
    'Client'
)

SERVER_MESSAGE_RE = re.compile(r':(?P<prefix>[\w\.]+) (?P<code>\d{3}) (?P<user>\w+) (?P<args>.+)?:(?P<params>.+)')
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

        self.logger = logging.getLogger(__name__)

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

        def check(message: ServerMessage):
            return message.code == Response(1)

        await self.wait_for('server_message', check=check, timeout=10)
        self.logger.info('Logged in as %s', username)

    async def recieve_loop(self) -> None:
        while True:
            data = await self.reader.readuntil(b'\r\n')
            self.loop.create_task(
                self.handle_recieve(data)
            )

    async def handle_recieve(self, data: bytes) -> None:
        data = data.decode()
        await self.dispatch('raw_socket_recieve', data)

    async def dispatch(self, event: str, *args, **kwargs) -> None:
        if waiters := self._waiters.get(event):
            for waiter in waiters:
                check = waiter[1]
                if check(*args, **kwargs):
                    waiter[0].set_result(*args, **kwargs)
                del waiter

        func = getattr(self, f'on_{event}')  # TODO: Make this actually have a proper listener / event system
        await func(*args, **kwargs)

    async def wait_for(
        self,
        event: str,
        *,
        timeout: int = None,
        check: Callable = None
    ) -> any:
        future = self.loop.create_future()

        if not self._waiters.get(event):
            self._waiters[event] = []

        if not check:
            def _(*args, **kwargs) -> bool:
                return True
            check = _

        self._waiters[event].append((future, check))
        return await asyncio.wait_for(future, timeout)

    async def send_command(
        self,
        command: str,
        *,
        args: str = None,
        params: str = None
    ) -> None:
        args = f'{args.strip()} ' if args else ''
        params = f':{params.strip()}' if params else ''
        message = f'{command.strip()} {args}{params}\r\n'
        logging.debug('Sent command %s', message.rstrip())
        await self.send_raw(message.encode())

    async def send_raw(self, data: bytes) -> None:
        self.writer.write(data)
        await self.writer.drain()

    async def on_raw_socket_recieve(self, message: str) -> None:

        if match := re.match(SERVER_MESSAGE_RE, message):  # Server message
            match_dict = match.groupdict()
            match_dict['code'] = int(match_dict['code'])
            message = ServerMessage(**match_dict)
            await self.dispatch('server_message', message)

        elif match := re.match(MESSAGE_RE, message):  # User message
            await self.dispatch('message', Message(**match.groupdict()))

        else:
            self.logger.warning('Recieved an unknown event: %s', message.rstrip())

    async def on_server_message(self, message):
        self.logger.debug('Recieved server message %s', message)

    async def on_message(self, message: Message) -> None:
        self.logger.debug('[{0.created_at}] {0.channel} - {0.nick} | {0.message}'.format(message))

    async def close(self, reason: str = None) -> None:
        await self.send_command('QUIT', params=reason)
        self._recieve_task.cancel()
        self.writer.close()
        await self.writer.wait_closed()

    async def set_nick(self, new_nick: str) -> None:
        await self.send_command('NICK', args=new_nick)

    async def join_channel(self, name: str) -> None:
        await self.send_command('JOIN', args=name)

        def check(message: Message) -> bool:
            return message.code == Response(353)

        message = await self.wait_for('server_message', check=check)
        self.logger.info('Joined %s with %s members', name, len(message.params.split()))

    async def send_message(self, channel: str, message: str) -> None:
        await self.send_command('PRIVMSG', args=channel, params=message)
