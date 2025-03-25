from livekit import api
import os
from dotenv import load_dotenv
import sys

load_dotenv(dotenv_path="../.env.local")

# Get room name from command line argument, default to "my-room" if not provided
room_name = "my-room"
if len(sys.argv) > 1:
    room_name = sys.argv[1]

# will automatically use the LIVEKIT_API_KEY and LIVEKIT_API_SECRET env vars
token = (
    api.AccessToken()
    .with_identity("python-bot-1")
    .with_name("Python Bot")
    .with_grants(
        api.VideoGrants(
            room_join=True,
            room=room_name,
        )
    )
    .to_jwt()
)

print(token)
