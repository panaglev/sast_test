import os
import pika
import requests

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt


# Решил вынести отправку в очередь в другую функцию
# т.к. это только в этом приложении один обработчик
# на практике может встретиться в разы больше - следовательно
# лучше подумать о переиспользовании кода
def send_to_scan(git_url: str):
    try:
        credentials = pika.PlainCredentials(
            os.getenv("RABBITMQ_USER"), os.getenv("RABBITMQ_PASS")
        )

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST"),
                port=os.getenv("RABBITMQ_PORT"),
                credentials=credentials,
            )
        )
        channel = connection.channel()

        channel.queue_declare(queue="links_to_scan")

        channel.basic_publish(exchange="", routing_key="links_to_scan", body=git_url)
    except Exception as e:
        return JsonResponse({"error": "Try later"})
    finally:
        connection.close()


@csrf_exempt
def check_repo(request):
    if request.POST:
        try:
            git_url = request.POST["url"]
            req = requests.get(git_url)
        except Exception as e:
            return JsonResponse({"error": "Problem with url"})

        if req.ok and (
            git_url.removeprefix("http://").removeprefix("https://").split(".")[0]
            in ("github", "gitlab")
        ):
            send_to_scan(git_url)
        else:
            return JsonResponse({"error": "Failed to send to scan"})

        return HttpResponse("Waiting to start the SAST")
    else:
        return JsonResponse({"error": "Method is not allowed"})


def index(request):
    return render(request, "app/index.html")
