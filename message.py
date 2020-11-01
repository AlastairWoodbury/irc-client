from datetime import datetime
from enums import Response

__all__ = (
    'ServerMessage'
)


class ServerMessage:
    def __init__(
        self,
        prefix: str,
        code: int,
        user: str,
        params: str,
    ) -> None:
        self.prefix = prefix
        self.code = Response(code)
        self.user = user
        self.params = params.rstrip()

    def __str__(self):
        return f':{self.prefix} {str(self.code.value).rjust(3, "0")} {self.user} :{self.params}'

    def __repr__(self):
        return '<ServerMessage prefix="{0.prefix}" code={0.code} user="{0.user}" params="{0.params}">'.format(self)


class Message:
    def __init__(
        self,
        nick: str,
        username: str,
        host: str,
        channel: str,
        message: str,
        *,
        created_at: datetime = None
    ) -> None:
        self.nick = nick
        self.username = username
        self.host = host
        self.channel = channel
        self.message = message
        self.created_at = created_at or datetime.now()

    @property
    def private(self):
        return self.channel[0] != '#'
