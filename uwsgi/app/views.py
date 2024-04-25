import os
import pika
import json
import requests

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings


def send_to_queue(data: str, queue_name: str):
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

        channel.queue_declare(queue=queue_name)

        channel.basic_publish(exchange="", routing_key=queue_name, body=data)
    except Exception as e:
        return None
    finally:
        connection.close()


def get_data_from_queue():
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

    channel.queue_declare(queue=settings.FINDINGS)

    findings = []

    def recieve_project_info_handle(ch, method, properties, body):
        data = body.decode()
        findings.append(data)
        channel.stop_consuming()

    channel.basic_consume(
        queue=settings.FINDINGS,
        on_message_callback=recieve_project_info_handle,
        auto_ack=True,
    )

    print("Waiting for messages. To exit, press CTRL+C")
    channel.start_consuming()

    return findings


def render_exact_project(request, project_name):
    send_to_queue(project_name, settings.PROJECTS_TO_PARSE)
    recieved_data = get_data_from_queue()
    json_recieved_data = recieved_data[0]
    parsed_data = json.loads(json_recieved_data)

    title = project_name

    if parsed_data != []:
        body = {"data": parsed_data, "title": title}
        return render(request, "app/project.html", context=body)
    else:
        return render(request, "app/project.html", context={"info": "no vulns found"})


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
            # if send_to_queue(git_url, "links_to_scan") is None:
            send_to_queue(git_url, settings.LINKS_TO_SCAN)
        else:
            return JsonResponse({"error": "Failed to send to scan"})

        return HttpResponse(
            "Info could be found on project page: http://127.0.0.1:8000/*project_name*"
        )
    else:
        return JsonResponse({"error": "Method is not allowed"})


def index(request):
    return render(request, "app/index.html")
