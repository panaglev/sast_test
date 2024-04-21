import os
import git
import pika
import json
import subprocess

FINDINGS = "findings"
PROJECTS_TO_PARSE = "projects_to_parse"
LINKS_TO_SCAN = "links_to_scan"


def get_repo_name_from_url(url: str) -> str:
    last_slash_index = url.rfind("/")
    last_suffix_index = url.rfind(".git")
    if last_suffix_index < 0:
        last_suffix_index = len(url)

    if last_slash_index < 0 or last_suffix_index <= last_slash_index:
        raise Exception("Badly formatted url {}".format(url))

    return url[last_slash_index + 1 : last_suffix_index]


def extract_project_vulns(project_name):
    findings = list()
    tmp = dict()
    prev_change = ""

    with open(f"/app/reports/{project_name}.txt", "r") as f:
        text = f.read()
        text = text.strip().split("\n")

        for line in text:
            line = line.strip()

            if line.startswith("/app/repos"):
                if prev_change == "line_in_code":
                    findings.append(dict(tmp))

                tmp = {"path": line, "vuln_name": "", "line_in_code": ""}
                prev_change = "path"

            elif line.startswith("❯❯❱") or line.startswith("❯❱"):
                if prev_change == "line_in_code":
                    findings.append(dict(tmp))

                tmp["vuln_name"] = line
                prev_change = "vuln_name"

            elif line != "" and line[0].isdigit():
                if prev_change == "line_in_code":
                    tmp["line_in_code"] += line
                    prev_change = "line_in_code"
                elif prev_change == "vuln_name":
                    tmp["line_in_code"] = line
                    prev_change = "line_in_code"

            else:
                continue

    return findings


def send_repo_to_scan(git_url: str):
    git_repo_name = get_repo_name_from_url(git_url)
    repo_path = os.path.join("/app/repos/", git_repo_name)

    try:
        if not os.path.exists(repo_path):
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


def main():
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

    def start_scan_handle(ch, method, properties, body):
        git_url = body.decode()
        send_repo_to_scan(git_url)

    channel.queue_declare(queue=LINKS_TO_SCAN)
    channel.basic_consume(
        queue=LINKS_TO_SCAN, on_message_callback=start_scan_handle, auto_ack=True
    )

    def return_project_info_handle(ch, method, properties, body):
        project_name = body.decode()
        result = extract_project_vulns(project_name)
        send_to_queue(json.dumps(result), FINDINGS)

    channel.queue_declare(queue=PROJECTS_TO_PARSE)
    channel.basic_consume(
        queue=PROJECTS_TO_PARSE,
        on_message_callback=return_project_info_handle,
        auto_ack=True,
    )

    print("Waiting for messages. To exit, press CTRL+C")
    channel.start_consuming()


if __name__ == "__main__":
    main()
