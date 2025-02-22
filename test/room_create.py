from livekit import api
import asyncio


import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env.local")


async def main():
    lkapi = api.LiveKitAPI("wss://rita-test-1uikzu5h.livekit.cloud")
    room_info = await lkapi.room.create_room(
        api.CreateRoomRequest(name="my-room"),
    )
    print(room_info)
    results = await lkapi.room.list_rooms(api.ListRoomsRequest())
    print(results)
    await lkapi.aclose()


asyncio.run(main())
