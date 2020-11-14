from __future__ import annotations

from typing import TYPE_CHECKING, List

from message import Message

if TYPE_CHECKING:
    import client


__all__ = (
    'Channel'
)


class Channel:
    def __init__(
        self,
        *,
        name: str,
        description: str = None,
        members: List[str],
        client: client.Client
    ) -> None:
        self.name = name
        self.description = description
        self.members = members
        self._client = client

    @property
    def private(self) -> bool:
        return not self.name.startswith('#')

    @property
    def member_count(self) -> int:
        return len(self.members)

    async def send(self, message: str) -> Message:
        await self._client.send_message(self.name, message)

    def __repr__(self) -> str:
        return '<Channel name="{0.name}" description="{0.description}" member_count="{0.member_count}">'.format(self)
