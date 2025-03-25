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
def home(request):
    return HttpResponse("Welcome to the test backend!")


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("test/", test_post, name="test_post"),
    path("stream/", start_stream_video, name="start_stream_video"),
]
