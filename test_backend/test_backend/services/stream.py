import asyncio
import colorsys
import logging
import os
from signal import SIGINT, SIGTERM
from time import perf_counter
import numpy as np
from livekit import api, rtc
import cv2
import wave

from django.conf import settings

# video_path = os.path.join(
#     settings.BASE_DIR, "test_backend", "videos", "countdown_360p.mp4"
# )
# audio_path = os.path.join(
#     settings.BASE_DIR, "test_backend", "videos", "test.wav"
# )
video_path = os.path.join(settings.BASE_DIR, "test_backend", "videos", "sync.mp4")
audio_path = os.path.join(settings.BASE_DIR, "test_backend", "videos", "sync.wav")
print(f"Video path: {video_path}")
print(f"Audio path: {audio_path}")


WIDTH, HEIGHT = 1280, 720
FPS = 25
VIDEO_PATH = video_path

# audio part
AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
QUEUE_SIZE_MS = 50


async def publish_video_frames(room, source_path):
    # Create video source and track
    source = rtc.VideoSource(WIDTH, HEIGHT)
    track = rtc.LocalVideoTrack.create_video_track("video", source)
    audio_source = rtc.AudioSource(
        AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, queue_size_ms=QUEUE_SIZE_MS
    )
    audio_track = rtc.LocalAudioTrack.create_audio_track("audio", audio_source)

    options = rtc.TrackPublishOptions(
        source=rtc.TrackSource.SOURCE_CAMERA,
        simulcast=True,
        video_encoding=rtc.VideoEncoding(
            max_framerate=FPS,
            max_bitrate=3_000_000,
        ),
    )

    # comment for now, maybe we use the AVsynchronizer later
    # publication = await room.local_participant.publish_track(track, options)
    await room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_CAMERA)
    )
    await room.local_participant.publish_track(
        audio_track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )

    # logging.info("published track %s", publication.sid)

    av_sync = rtc.AVSynchronizer(
        audio_source=audio_source,
        video_source=source,
        video_fps=FPS,
        video_queue_size_ms=QUEUE_SIZE_MS,
    )

    # open video file
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        logging.error("Error: Could not open video file")
        return

    # open audio video
    # Open audio file
    wf = wave.open(audio_path, "rb")
    audio_chunk_size = (
        int(AUDIO_SAMPLE_RATE / FPS) * AUDIO_CHANNELS * 2
    )  # Bytes per frame

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

            audio_data = wf.readframes(audio_chunk_size // (AUDIO_CHANNELS * 2))
            if not audio_data:
                break  # End of audio
            audio_frame = rtc.AudioFrame(
                data=audio_data,
                sample_rate=AUDIO_SAMPLE_RATE,
                num_channels=AUDIO_CHANNELS,
                samples_per_channel=len(audio_data) // (2 * AUDIO_CHANNELS),
            )

            # Calculate delay to maintain FPS
            frame_count += 1
            elapsed = perf_counter() - start_time
            target_time = frame_count / FPS
            if elapsed < target_time:
                await asyncio.sleep(target_time - elapsed)

            # send_frame
            await av_sync.push(video_frame)
            await av_sync.push(audio_frame)

    finally:
        cap.release()

        ####
        wf.close()
        await av_sync.aclose()
        await source.aclose()
        await audio_source.aclose()


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
