import asyncio
import logging

from client import Client

logging.basicConfig(level=logging.DEBUG)


async def main():
    client = Client(
        username='',
        nick='',
        password=''
    )

    await client.connect('')
    await client.join_channel('')
    channel = client.get_channel('')
    await channel.send('Hi!')
    await asyncio.sleep(30)
    await client.close('Bye!')

if __name__ == "__main__":
    asyncio.run(main(), debug=True)
