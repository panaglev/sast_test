import os
import pika
import requests

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

# Create your views here.


@csrf_exempt
def check_repo(request):
    if request.POST:
        # Пробуем извлечь ссылку
        # Оборачиваем в try-catch потому что этого поля в запросе может и не быть (если прорабатывать все сайд-кейсы)
        try:
            git_url = request.POST["url"]
        except Exception as e:
            # Можно в лог записать e, а пользователю отобразить вот так
            return JsonResponse({"error": "No url specified"})

        # Пробуем получить ответ по той ссылке которую нам передал пользователь
        # Оборачиваем в try-catch потому что может быть передана не только ссылка
        try:
            req = requests.get(git_url)
        except Exception as e:
            # Точно так же можно в лог записать
            return JsonResponse({"error": "Seems this is not a url"})

        # Если прошлые проверки прошли - значит в запросе была ссылка и это была именно ссылка,
        # но на данном этапе нет уверенности, что это ссылка именно на гит.
        # Поэтому проверим ссылка ли это на гит и успешный ли запрос или нет
        if req.ok and (
            git_url.removeprefix("http://").removeprefix("https://").split(".")[0]
            in ("github", "gitlab")
        ):
            # Устанавливаем параметры подключения до кролика
            try:
                credentials = pika.PlainCredentials(
                    os.getenv("RABBITMQ_USER"), os.getenv("RABBITMQ_PASS")
                )
            except Exception as e:
                # В лог записываем, что ошибка с кроликом. Пользователю это знать не обязательно - возвращаем общую ошибку
                return JsonResponse({"error": "Some error occured"})

            # Пытаемся подкючиться к кролику
            try:
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=os.getenv("RABBITMQ_HOST"),
                        port=os.getenv("RABBITMQ_PORT"),
                        credentials=credentials,
                    )
                )
                channel = connection.channel()
            except Exception as e:
                return JsonResponse({"error": "Some error occured"})

            # Объявляем очередь
            try:
                channel.queue_declare(queue="links_to_scan")
            except Exception as e:
                return JsonResponse({"error": "Some error occured"})

            # Отправляем ссылку на репозиторий гит в очередь
            try:
                channel.basic_publish(
                    exchange="", routing_key="links_to_scan", body=git_url
                )
            except Exception as e:
                return JsonResponse({"error": "Some error occured"})

            # Закрываем подключение
            connection.close()
        else:
            return JsonResponse({"error": "Seems this is not a git link"})

        return HttpResponse("Waiting to start the SAST")
    else:
        return JsonResponse({"error": "Method is not allowed"})


def index(request):
    return render(request, "app/index.html")
