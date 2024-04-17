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
    # At this point we're sure that git_url contains valid url on git repo
    # All we need to do is to download project and start scan
    repo = git.Repo.clone_from(git_url, "/app/worker/repos", branch="main")

    if repo:
        pass
    else:
        return None


channel.basic_consume(
    queue="links_to_scan", on_message_callback=callback, auto_ack=True
)

print("Waiting for messages. To exit, press CTRL+C")
channel.start_consuming()
