"""Docker container health monitoring script with Gmail alerting."""

import os
import sys
import subprocess
import datetime
import base64
import json
import logging
from subprocess import TimeoutExpired
from email.mime.text import MIMEText

import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build

# === CONFIGURATION ===
CONFIG_FILE = "config.yaml"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def load_config():
    """Load configuration from the YAML config file."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except (FileNotFoundError, yaml.YAMLError) as err:
        print(f"Failed to load config file '{CONFIG_FILE}': {err}")
        sys.exit(1)


CONFIG = load_config()

SERVER = CONFIG.get("server", "unspecified")
CONTAINER_NAMES = CONFIG.get("containers", [])
ALERT_EMAIL = CONFIG.get("alert_email")
FROM_EMAIL = CONFIG.get("from_email")
DELEGATED_USER = CONFIG.get("delegated_user")
STATE_FILE = CONFIG.get("state_file", "container_status.json")
SERVICE_ACCOUNT_FILE = CONFIG.get("service_account_file", "service_account.json")
DOCKER_TIMEOUT = CONFIG.get("docker_timeout", 10)

# Internal state for unhealthy container statuses
UNHEALTHY_STATES = ["unhealthy", "exited", "timeout", "unknown"]

# === LOGGING CONFIGURATION ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


def authenticate_gmail_service():
    """Authenticate with Gmail API using a service account."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    ).with_subject(DELEGATED_USER)

    return build("gmail", "v1", credentials=creds)


def get_container_health(container_name):
    """Inspect Docker container and return its health status."""
    try:
        result = subprocess.check_output(
            [
                "docker",
                "inspect",
                "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
                container_name,
            ],
            stderr=subprocess.DEVNULL,
            timeout=DOCKER_TIMEOUT,
        )
        return result.decode().strip()
    except TimeoutExpired:
        logging.error("Timeout while checking container '%s'", container_name)
        return "timeout"
    except subprocess.CalledProcessError as err:
        logging.debug("Error checking container '%s': %s", container_name, err)
        return "unknown"


def send_alert(service, container_name, status):
    """Send an email alert about the container's unhealthy status."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"[ALERT {SERVER}] '{container_name}' is {status}"
    body = (
        f"The Docker container `{container_name}` is in an **{status.upper()}** state as of {now}.\n\n"
        "Please check the logs and take necessary action."
    )

    message = MIMEText(body)
    message["to"] = ALERT_EMAIL
    message["from"] = FROM_EMAIL
    message["subject"] = subject

    raw_message = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
    response = service.users().messages().send(userId="me", body=raw_message).execute()

    logging.info("Alert sent for '%s' (status: %s)", container_name, status)
    logging.debug("Gmail API response: %s", response)


def load_statuses():
    """Load previous container statuses from file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def save_statuses(statuses):
    """Save container statuses to file."""
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(statuses, file, indent=2)


def main():
    """Main execution logic."""
    if not CONTAINER_NAMES:
        logging.error("No containers configured in %s", CONFIG_FILE)
        return

    service = authenticate_gmail_service()
    last_statuses = load_statuses()
    new_statuses = {}

    for container in CONTAINER_NAMES:
        status = get_container_health(container)
        logging.debug("Container '%s' status: %s", container, status)

        last_status = last_statuses.get(container, "unavailable")

        if status in UNHEALTHY_STATES and last_status not in UNHEALTHY_STATES:
            send_alert(service, container, status)
        else:
            logging.debug("No alert sent: '%s' unchanged (%s)", container, status)

        new_statuses[container] = status

    save_statuses(new_statuses)

    unhealthy_now = {c: s for c, s in new_statuses.items() if s in UNHEALTHY_STATES}
    logging.info(
        "Monitoring complete. %d container(s) in unhealthy state.", len(unhealthy_now)
    )


if __name__ == "__main__":
    main()
