import os
import git
import pika

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
    git_repo_name = git_url.removesuffix(".git").split("/")[-1]
    repo = git.Repo.clone_from(
        git_url, f"/app/worker/repos/{git_repo_name}", branch="main"
    )

    if repo:
        pass
    else:
        return None


channel.basic_consume(
    queue="links_to_scan", on_message_callback=callback, auto_ack=True
)

print("Waiting for messages. To exit, press CTRL+C")
channel.start_consuming()
