import asyncio

from client import Client


async def main():
    client = Client(
        username='',
        nick='',
        password=''
    )

    await client.connect('')
    await asyncio.sleep(2)
    await client.join_channel('')
    await asyncio.sleep(2)
    await client.send_message('', '')
    await asyncio.sleep(30)
    await client.close('')

if __name__ == "__main__":
    asyncio.run(main())
