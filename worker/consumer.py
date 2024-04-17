import os
import git
import pika
import subprocess

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


def callback(ch, method, properties, body):
    git_url = body.decode()
    # Тут мы получаем название репозитория
    git_repo_name = git_url.removesuffix(".git").split("/")[-1]

    # Пытаемся склонить. Обернул в try-catch потому что всякое бывает, может интернет пропадет
    try:
        repo = git.Repo.clone_from(
            git_url, f"/app/worker/repos/{git_repo_name}", branch="main"
        )
    except Exception as e:
        print("Ошибка при клонировании репозитория")
        return None

    # Не уверен, что так вылавливается ошибка на склоненный репо... Типа даже если ошибка будет, то она все ранво что-то запишет в переменную и уже не ноль
    if repo:
        commands = [
            "bash",
            "-c",
            f"cd /app/worker/repos/{git_repo_name} && semgrep scan >> ../../reports/result_{git_repo_name}.txt",
        ]
        result = subprocess.run(commands)
        if result.returncode != 0:
            print("Не удалось просканировать проект")
    else:
        return None


channel.basic_consume(
    queue="links_to_scan", on_message_callback=callback, auto_ack=True
)

print("Waiting for messages. To exit, press CTRL+C")
channel.start_consuming()
