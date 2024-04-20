import os
import re
import git
import pika
import subprocess


def get_repo_name_from_url(url: str) -> str:
    last_slash_index = url.rfind("/")
    last_suffix_index = url.rfind(".git")
    if last_suffix_index < 0:
        last_suffix_index = len(url)

    if last_slash_index < 0 or last_suffix_index <= last_slash_index:
        raise Exception("Badly formatted url {}".format(url))

    return url[last_slash_index + 1 : last_suffix_index]


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

    git_repo_name = get_repo_name_from_url(git_url)
    repo_path = os.path.join("/app/repos/", git_repo_name)

    try:
        if os.path.exists(repo_path) == False:
            _ = git.Repo.clone_from(git_url, repo_path)
    except Exception as e:
        return None

    commands = [
        "bash",
        "-c",
        f"echo ====NEW_SCAN==== >> /app/reports/{git_repo_name}.txt && semgrep scan /app/repos/{git_repo_name} >> /app/reports/{git_repo_name}.txt",
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
