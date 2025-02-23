import asyncio
import colorsys
import logging
import os
from signal import SIGINT, SIGTERM
from time import perf_counter
import numpy as np
from livekit import api, rtc
import cv2

from django.conf import settings

video_path = os.path.join(
    settings.BASE_DIR, "test_backend", "videos", "countdown_360p.mp4"
)
print(f"Video path: {video_path}")


WIDTH, HEIGHT = 1280, 720
FPS = 30
VIDEO_PATH = video_path


async def publish_video_frames(room, source_path):
    # Create video source and track
    source = rtc.VideoSource(WIDTH, HEIGHT)
    track = rtc.LocalVideoTrack.create_video_track("video", source)
    options = rtc.TrackPublishOptions(
        source=rtc.TrackSource.SOURCE_CAMERA,
        simulcast=True,
        video_encoding=rtc.VideoEncoding(
            max_framerate=FPS,
            max_bitrate=3_000_000,
        ),
    )
    publication = await room.local_participant.publish_track(track, options)
    logging.info("published track %s", publication.sid)

    print("source_path is: " + source_path)
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        logging.error("Error: Could not open video file")
        return

    start_time = perf_counter()
    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Resize frame if needed to match WIDTH x HEIGHT
            frame = cv2.resize(frame, (WIDTH, HEIGHT))

            # Convert BGR to RGBA (LiveKit expects RGBA)
            frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)

            # Create VideoFrame and capture
            video_frame = rtc.VideoFrame(
                WIDTH, HEIGHT, rtc.VideoBufferType.RGBA, frame_rgba.tobytes()
            )

            # Calculate delay to maintain FPS
            frame_count += 1
            elapsed = perf_counter() - start_time
            target_time = frame_count / FPS
            if elapsed < target_time:
                await asyncio.sleep(target_time - elapsed)

            # send_frame
            source.capture_frame(video_frame)

    finally:
        cap.release()
        # await track.stop()


async def connect_and_stream(token, video_path):
    room = rtc.Room()
    try:
        url = os.getenv("LIVEKIT_URL")
        await room.connect(url=url, token=token)
        logging.info("Connected to room: %s", room.name)

        # Stream video once
        for _ in range(1):
            await publish_video_frames(room, video_path)
            logging.info("Completed video loop iteration")

    finally:
        await room.disconnect()


def stream_video(room_name: str):
    print(f"Starting video stream for room: {room_name}")

    token = (
        api.AccessToken()
        .with_identity("python-publisher")
        .with_name("Python Publisher")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
        .to_jwt()
    )

    # Video file path
    video_path = VIDEO_PATH  # Update this path

    # Run the async function
    asyncio.run(connect_and_stream(token, video_path))

    print("Video streaming completed")
