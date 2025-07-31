import os
import subprocess
import datetime
import base64
import json
import logging
from email.mime.text import MIMEText
from google.oauth2 import service_account
from googleapiclient.discovery import build

# === CONFIGURATION ===
SERVER = "internal"
CONTAINER_NAMES = ["sustainable_steps-front-1",
                   "vaultwarden",
                   "farm_wiki-nginx-1",
                   "pihole"
                  ]

# Recipient
ALERT_EMAIL = "jens@farmurban.co.uk"
FROM_EMAIL = "jens@farmurban.co.uk"  # Appears in the "From" field

# Service account config
DELEGATED_USER = "jens@farmurban.co.uk"
STATE_FILE = "container_status.json"
SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# === LOGGING CONFIGURATION ===
LOG_LEVEL = logging.INFO
LOG_FILE = "docker_monitor.log"

UNHEALTHY = ["unhealthy", "exited", "unknown"]

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        # log to stdout and let systemd handle logs
        #logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def authenticate_gmail_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    ).with_subject(DELEGATED_USER)

    service = build("gmail", "v1", credentials=creds)
    return service

def get_container_health(name):
    try:
        result = subprocess.check_output(
            ["docker", "inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", name],
            stderr=subprocess.DEVNULL
        )
        return result.decode().strip()
    except subprocess.CalledProcessError as e:
        logging.debug(f"Error checking container status: {e}")
        return "unknown"

def send_alert(service, container, status):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"[ALERT {SERVER}] '{container}' is {status}"
    body = f"""
The Docker container `{container}` is in an **{status.upper()}** state as of {now}.

Please check the logs and take necessary action.
"""
    message = MIMEText(body)
    message["to"] = ALERT_EMAIL
    message["from"] = FROM_EMAIL
    message["subject"] = subject

    raw = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}

    response = service.users().messages().send(userId="me", body=raw).execute()
    logging.info(f"[{now}] Alert sent for {container}: {status}")
    logging.debug(f"Response from service: {response}")

def load_statuses():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_statuses(statuses):
    with open(STATE_FILE, "w") as f:
        json.dump(statuses, f, indent=2)

def main():
    service = authenticate_gmail_service()
    last_statuses = load_statuses()
    new_statuses = {}

    for container in CONTAINER_NAMES:
        status = get_container_health(container)
        logging.debug(f"Container '{container}' health status: {status}")
        last_status = last_statuses.get(container, "unavailable")

        # Trigger alert only on transition to unhealthy
        if status in UNHEALTHY and last_status not in UNHEALTHY:
            send_alert(service, container, status)
        else:
            logging.debug(f"No alert sent: '{container}' status unchanged ({status})")

        new_statuses[container] = status

    save_statuses(new_statuses)

if __name__ == "__main__":
    main()

