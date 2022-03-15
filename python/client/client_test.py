import asyncio

async def tcp_echo_client(message):
    reader, writer = await asyncio.open_connection(
        '10.216.68.189', 12347)

    print(f'Send: {message!r}')
    writer.write(message.encode())

    data = await reader.read(100)
    print(f'Received: {data.decode()!r}')

    print('Close the connection')
    writer.close()

asyncio.run(tcp_echo_client('Hello World!'))