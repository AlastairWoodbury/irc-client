import asyncio
import logging
import re
from typing import Any, Callable, Optional

from channel import Channel
from enums import Response
from message import Message, PingMessage, ServerMessage

__all__ = (
    'Client'
)

SERVER_MESSAGE_RE = re.compile(r':(?P<prefix>[\w\.]+) (?P<code>[^ ]+) (?P<user>[^ ]+) (?:(?P<args>.+) )?:(?P<params>.+)\r\n')
MESSAGE_RE = re.compile(r':(?P<nick>.+)!(?P<username>.+)@(?P<host>.+) (?P<content>.+) (:?(?P<args>.+) )?:(?P<params>.+)\r\n')
PING_RE = re.compile(r'PING :(?P<params>.+)\r\n')


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
        self._listensers = {}
        self._channels = {}

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
            self.recieve_loop(),
            name='recieve'
        )

        password = password if password is not ... else self.password
        username = username if username is not ... else self.username
        nick = nick if nick is not ... else self.nick

        await self.set_nick(nick)
        await self.send_command(
            'USER',
            args=f'{username} * *',
            params=password
        )

        await self.wait_for(
            'server_message',
            check=lambda message: message.code == Response.RPL_WELCOME,
            timeout=5
        )
        self.logger.info('Logged in as %s', username)

    async def recieve_loop(self) -> None:
        while True:
            data = await self.reader.readuntil(b'\r\n')
            await self.handle_recieve(data)

    async def handle_recieve(self, data: bytes) -> None:
        data = data.decode()
        await self.dispatch('raw_socket_recieve', data)

    async def dispatch(self, event: str, *args, **kwargs) -> None:
        if waiters := self._waiters.get(event):
            for waiter in waiters:
                future, check = waiter
                if check(*args, **kwargs):
                    future.set_result(*args, **kwargs)
                    waiters.remove(waiter)

        try:
            func = getattr(self, f'on_{event}')  # TODO: Make this actually have a proper listener / event system
        except AttributeError:
            pass
        else:
            await func(*args, **kwargs)

        if listeners := self._listensers.get(event):
            for listener in listeners:
                await listener(*args, **kwargs)

    async def wait_for(
        self,
        event: str,
        *,
        timeout: float = None,
        check: Callable = None
    ) -> Any:
        '''Wait for an event to happen

        Parameters:
          - event: str - The event to wait for
          - timout: float - The ammount of time to wait before raising `asyncio.TimeoutError`
          - check: Callable - A callable to filter events

        Raises:
          - asyncio.TimeoutError
        '''

        future = self.loop.create_future()

        if not self._waiters.get(event):
            self._waiters[event] = []

        if not check:
            def _(*args, **kwargs) -> bool:
                return True
            check = _

        self._waiters[event].append((future, check))
        return await asyncio.wait_for(future, timeout)

    async def accumulate(
        self,
        event: str,
        *,
        check: Callable = None,
        final: Callable = None,
        timeout: float = None
    ) -> Any:
        if check is None:
            def _(*args, **kwargs) -> bool:
                return True
            check = _

        if final is None:
            def _(*args, **kwargs) -> bool:
                return True
            final = _

        total = []
        fut = self.loop.create_future()

        async def _(*args, **kwargs):
            if check(*args, **kwargs):
                return total.append((args, kwargs))

            if final(*args, **kwargs):
                total.append((args, kwargs))
                return fut.set_result(1)

        self.add_listener(event, _)
        await asyncio.wait_for(fut, timeout)
        self.remove_listener(event, _)

        return total

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
        await self._send_raw(message.encode())

    async def _send_raw(self, data: bytes) -> None:
        self.writer.write(data)
        await self.writer.drain()

    def add_listener(
        self,
        event: str,
        coro: Callable
    ) -> None:
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('Listener callback must be a coroutine')

        if not self._listensers.get(event):
            self._listensers[event] = set()

        self._listensers[event].add(coro)

        return coro

    def remove_listener(
        self,
        event: str,
        coro: Callable
    ) -> Callable:
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('Listener must be a coroutine')

        self._listensers[event].remove(coro)

        return coro

    # ~~ Listeners ~~ #

    async def on_raw_socket_recieve(self, data: str) -> None:
        if match := re.match(MESSAGE_RE, data):
            await self.dispatch(
                'message',
                Message(data=match.groupdict())
            )

        elif match := re.match(SERVER_MESSAGE_RE, data):
            await self.dispatch(
                'server_message',
                ServerMessage(data=match.groupdict())
            )

        elif match := re.match(PING_RE, data):
            await self.dispatch(
                'ping',
                PingMessage(data=data)
            )

    async def on_ping(self, message: PingMessage) -> None:
        logging.debug('Sending ping message to %s', message.server)
        await self.send_command('PING', args=message.server)

    async def on_server_message(self, message: ServerMessage) -> None:
        ...

    # ~~ Helper Methods ~~ #

    async def set_nick(self, new_nick: str) -> None:
        await self.send_command('NICK', args=new_nick)

    async def join_channel(self, name: str) -> Channel:
        await self.send_command('JOIN', args=name)

        members = []

        messages = await self.accumulate(
            'server_message',
            check=lambda message: message.code == Response.RPL_NAMREPLY,
            final=lambda message: message.code == Response.RPL_ENDOFNAMES,
            timeout=10
        )
        for message in messages:
            if message[0][0].code == Response.RPL_NAMREPLY:
                for member in message[0][0].params.split():
                    members.append(member)

        self._channels[name] = Channel(
            name=name,
            members=members,
            client=self
        )

    async def send_message(self, channel: str, message: str) -> None:
        await self.send_command('PRIVMSG', args=channel, params=message)

    async def close(self, reason: str = None) -> None:
        await self.send_command('QUIT', params=reason)
        self._recieve_task.cancel()
        self.writer.close()
        await self.writer.wait_closed()

    def get_channel(
        self,
        channel: str
    ) -> Optional[Channel]:
        return self._channels.get(channel)
