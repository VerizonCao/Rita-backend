import asyncio
import colorsys
import logging
import os
from signal import SIGINT, SIGTERM
from time import perf_counter
import time

import numpy as np
from livekit import api, rtc

from dotenv import load_dotenv
import cv2

import subprocess

load_dotenv(dotenv_path="../.env.local")

WIDTH, HEIGHT = 1280, 720
FPS = 30

# ensure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are set


async def main(room: rtc.Room):

    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
    LIVEKIT_URL = os.getenv("LIVEKIT_URL")

    print(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL)

    token = (
        api.AccessToken()
        .with_identity("python-publisher-1")
        .with_name("Python Publisher")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room="my-room",
            )
        )
        .to_jwt()
    )
    url = os.getenv("LIVEKIT_URL")
    logging.info("connecting to %s", url)
    try:
        await room.connect(url, token)
        logging.info("connected to room %s", room.name)
    except rtc.ConnectError as e:
        logging.error("failed to connect to the room: %s", e)
        return

    # publish a track
    source = rtc.VideoSource(WIDTH, HEIGHT)
    track = rtc.LocalVideoTrack.create_video_track("hue", source)
    options = rtc.TrackPublishOptions(
        source=rtc.TrackSource.SOURCE_CAMERA,
        simulcast=True,
        video_encoding=rtc.VideoEncoding(
            max_framerate=FPS,
            max_bitrate=3_000_000,
        ),
    )
    print("before publish")
    publication = await room.local_participant.publish_track(track, options)
    print("finish publish")
    logging.info("published track %s", publication.sid)

    # asyncio.ensure_future(draw_color_cycle(source))
    # asyncio.ensure_future(draw_video_stream(source))
    asyncio.ensure_future(draw_video_stream_ffmpeg(source))

    # uncomment the below to test Track Subscription Permissions
    # https://docs.livekit.io/home/client/tracks/publish/#subscription-permissions
    # await asyncio.sleep(10)

    # logging.info(
    #     "setting track subscription permissions to False, no one can subscribe to the track"
    # )
    # room.local_participant.set_track_subscription_permissions(allow_all_participants=False)

    # await asyncio.sleep(10)

    # logging.info("allowing user to subscribe to the track")
    # room.local_participant.set_track_subscription_permissions(
    #     allow_all_participants=False,
    #     participant_permissions=[
    #         rtc.ParticipantTrackPermission(
    #             participant_identity="allowed-user-identity",
    #             allow_all=True,
    #         )
    #     ],
    # )


async def draw_color_cycle(source: rtc.VideoSource):
    argb_frame = bytearray(WIDTH * HEIGHT * 4)
    arr = np.frombuffer(argb_frame, dtype=np.uint8)

    framerate = 1 / FPS
    hue = 0.0
    next_frame_time = perf_counter()

    while True:
        rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        rgb = [(x * 255) for x in rgb]  # type: ignore

        argb_color = np.array(rgb + [255], dtype=np.uint8)
        arr.flat[::4] = argb_color[0]
        arr.flat[1::4] = argb_color[1]
        arr.flat[2::4] = argb_color[2]
        arr.flat[3::4] = argb_color[3]

        frame = rtc.VideoFrame(WIDTH, HEIGHT, rtc.VideoBufferType.RGBA, argb_frame)
        source.capture_frame(frame)
        hue = (hue + framerate / 3) % 1.0

        # code_duration = perf_counter() - start_time
        next_frame_time += 1 / FPS
        await asyncio.sleep(next_frame_time - perf_counter())
        # await asyncio.sleep(1 / FPS - code_duration)


async def draw_video_stream(source: rtc.VideoSource):
    # Open the video file
    video = cv2.VideoCapture("videos/test.mp4")
    if not video.isOpened():
        logging.error("Error: Could not open video file")
        return

    # Get video properties
    fps = video.get(cv2.CAP_PROP_FPS)
    framerate = 1 / FPS  # Use constant FPS instead of video's native FPS
    next_frame_time = perf_counter()

    while True:
        ret, frame = video.read()
        if not ret:
            # If we reach the end of the video, loop back to start
            video.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # Resize frame if needed to match WIDTH x HEIGHT
        frame = cv2.resize(frame, (WIDTH, HEIGHT))

        # Convert BGR to RGBA (LiveKit expects RGBA)
        frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)

        # Create VideoFrame and capture
        video_frame = rtc.VideoFrame(
            WIDTH, HEIGHT, rtc.VideoBufferType.RGBA, frame_rgba.tobytes()
        )
        source.capture_frame(video_frame)

        # Maintain constant frame rate
        next_frame_time += framerate
        await asyncio.sleep(max(0, next_frame_time - perf_counter()))


async def draw_video_stream_ffmpeg(source: rtc.VideoSource):
    VIDEO_PATH = "videos/countdown_360p.mp4"
    FRAMERATE = 1 / FPS

    # Start FFmpeg process to decode the video
    ffmpeg_cmd = [
        "ffmpeg",
        "-i",
        VIDEO_PATH,  # Input video file
        "-an",  # Ignore audio
        "-vf",
        f"scale={WIDTH}:{HEIGHT}",  # Resize video
        "-pix_fmt",
        "rgba",  # Output pixel format
        "-f",
        "rawvideo",  # Output raw video
        "-",  # Send output to stdout
    ]

    process = subprocess.Popen(
        ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8
    )

    if not process.stdout:
        logging.error("Error: FFmpeg did not start properly")
        return

    frame_size = WIDTH * HEIGHT * 4  # RGBA format
    next_frame_time = perf_counter()

    try:
        while True:
            raw_frame = process.stdout.read(frame_size)
            if not raw_frame:
                logging.info("End of video stream, restarting...")
                process.stdout.close()
                process.terminate()
                process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=10**8,
                )
                continue

            frame_rgba = np.frombuffer(raw_frame, dtype=np.uint8).reshape(
                (HEIGHT, WIDTH, 4)
            )

            # Create VideoFrame and capture
            video_frame = rtc.VideoFrame(
                WIDTH, HEIGHT, rtc.VideoBufferType.RGBA, frame_rgba.tobytes()
            )
            source.capture_frame(video_frame)

            # Maintain constant frame rate
            next_frame_time += FRAMERATE
            await asyncio.sleep(max(0, next_frame_time - perf_counter()))

    except Exception as e:
        logging.error(f"Error during video streaming: {e}")

    finally:
        process.terminate()
        process.wait()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler("publish_hue.log"), logging.StreamHandler()],
    )

    import threading
    import signal

    # Create an event to signal thread shutdown
    shutdown_event = threading.Event()

    def run_livekit():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        room = rtc.Room(loop=loop)

        async def cleanup():
            await room.disconnect()
            loop.stop()

        asyncio.ensure_future(main(room))

        try:
            loop.run_forever()
        finally:
            loop.close()

    # Signal handler for the main thread
    def signal_handler(signum, frame):
        print("Received signal, shutting down...")
        shutdown_event.set()

    # Set up signal handlers in main thread
    signal.signal(SIGINT, signal_handler)
    signal.signal(SIGTERM, signal_handler)

    # Create and start the thread
    livekit_thread = threading.Thread(target=run_livekit, daemon=True)
    livekit_thread.start()

    # Keep the main thread running until shutdown is signaled
    try:
        while not shutdown_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_event.set()

    print("Shutting down...")
