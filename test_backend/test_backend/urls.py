"""
URL configuration for test_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from test_backend.services.stream import stream_video
from test_backend.services.simple_agent import start_agent
from test_backend.services.basic_queue_method import start_queues
import json
import threading
from multiprocessing import Process
from subprocess import Popen, PIPE

worker_process = None


@csrf_exempt
def test_post(request):
    if request.method == "POST":
        print("123")
        return HttpResponse("Success")
    return HttpResponse("Method not allowed", status=405)


@csrf_exempt
def start_stream_video(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            room_name = data.get("room_name")

            if not room_name:
                return HttpResponse("room_name is required", status=400)

            # Start stream_video in a separate thread
            thread = threading.Thread(target=stream_video, args=(room_name,))
            thread.daemon = (
                True  # Make thread daemon so it exits when main thread exits
            )
            thread.start()

            return HttpResponse("Success")
        except json.JSONDecodeError:
            return HttpResponse("Invalid JSON", status=400)
    return HttpResponse("Method not allowed", status=405)


@csrf_exempt
def start_simple_agent(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            room_name = data.get("room_name")

            if not room_name:
                return HttpResponse("room_name is required", status=400)

            if 0:
                # Start stream_video in a separate thread
                thread = threading.Thread(target=start_agent, args=(room_name,))
                thread.daemon = (
                    True  # Make thread daemon so it exits when main thread exits
                )
                thread.start()
            else:
                # a different way, use subprocess to start a new program.
                global worker_process
                if worker_process is None or worker_process.poll() is not None:
                    worker_process = Popen(
                        [
                            "python",
                            "-c",
                            f'from test_backend.services.simple_agent import start_agent; start_agent("{room_name}")',
                        ],
                        stdout=None,  # Redirects output to the console
                        stderr=None,  # Redirects errors to the console
                    )
                    return HttpResponse("Worker started")
                return HttpResponse("Worker already running")

            return HttpResponse("Success")
        except json.JSONDecodeError:
            return HttpResponse("Invalid JSON", status=400)
    return HttpResponse("Method not allowed", status=405)


@csrf_exempt
def start_queue_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            room_name = data.get("room_name")

            if not room_name:
                return HttpResponse("room_name is required", status=400)

            # Start queues in a separate thread
            thread = threading.Thread(target=start_queues, args=(room_name,))
            thread.daemon = (
                True  # Make thread daemon so it exits when main thread exits
            )
            thread.start()

            return HttpResponse("Success")
        except json.JSONDecodeError:
            return HttpResponse("Invalid JSON", status=400)
    return HttpResponse("Method not allowed", status=405)


@csrf_exempt
def home(request):
    return HttpResponse("Welcome to the test backend!")


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("test/", test_post, name="test_post"),
    path("stream/", start_stream_video, name="start_stream_video"),
    path("simple_agent/", start_simple_agent, name="start_simple_agent"),
    path("start_queues/", start_queue_view, name="start_queues"),
]
