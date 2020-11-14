from datetime import datetime

from enums import Response

__all__ = (
    'ServerMessage'
)


class ServerMessage:
    def __init__(
        self,
        *,
        data: dict
    ) -> None:
        self.prefix = data.get('prefix')
        self.code = Response(data.get('code'))
        self.user: str = data.get('user')
        self.args = data.get('args')
        self.params = data.get('params')

    def __str__(self):
        return f':{self.prefix} {str(self.code.value).rjust(3, "0")} {self.user} {f"{self.args} " if self.args is not None else ""}:{self.params}'

    def __repr__(self):
        return '<ServerMessage prefix="{0.prefix}" code={0.code} user="{0.user}" args="{0.args}" params="{0.params}">'.format(self)


class Message:
    def __init__(
        self,
        *,
        data: dict
    ) -> None:
        self.nick: str = data.get('nick')
        self.username: str = data.get('username')
        self.host: str = data.get('host')
        self.channel: str = data.get('channel')
        self.message: str = data.get('message')
        self.created_at = data.get('created_at') or datetime.now()

    @property
    def private(self):
        return self.channel.startswith('#')


class PingMessage:
    def __init__(
        self,
        *,
        data: dict
    ) -> None:
        self.host: str = data.get('host')

    def __repr__(self) -> str:
        return f'<PingMessage{f" Server={self.server}" if self.server is not None else ""}>'
