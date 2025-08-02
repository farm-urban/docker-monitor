"""Script to montior Docker containers on host and alert on status,"""

import os
import sys
import time
import datetime
import base64
import json
import logging
from email.mime.text import MIMEText
from typing import Dict, List

import yaml
import docker
from google.oauth2 import service_account
from googleapiclient.discovery import build

# === CONFIGURATION ===
CONFIG_FILE = "/app/config.yaml"


def load_config() -> Dict:
    """Load configuration from a YAML file."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except (FileNotFoundError, yaml.YAMLError) as err:
        logging.error("Failed to load config file '%s': %s", CONFIG_FILE, err)
        sys.exit(1)


CONFIG = load_config()

SERVER = CONFIG.get("server", os.getenv("DOCKER_HOSTNAME", "unspecified-host"))
CONTAINER_NAMES = CONFIG.get("containers", [])
ALERT_EMAIL = CONFIG.get("alert_email")
FROM_EMAIL = CONFIG.get("from_email")
DELEGATED_USER = CONFIG.get("delegated_user")
POLL_INTERVAL = CONFIG.get("poll_interval", 300)  # seconds
LOG_LEVEL = CONFIG.get("log_level", "INFO").upper()
STATE_DIR = "/app/status"
STATE_FILE = os.path.join(STATE_DIR, "container_status.json")
UNHEALTHY_STATES = ["unhealthy", "exited", "timeout", "unknown"]

SERVICE_ACCOUNT_FILE = "/app/service_account.json"
if not os.path.isfile(SERVICE_ACCOUNT_FILE):
    raise FileNotFoundError(
        f"Service account file '{SERVICE_ACCOUNT_FILE}' not found. "
        "Please ensure it is mounted correctly."
    )

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


def authenticate_gmail_service():
    """Authenticate and return a Gmail API service object."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/gmail.send"]
    ).with_subject(DELEGATED_USER)
    return build("gmail", "v1", credentials=creds)


def get_container_health(container_name: str) -> str:
    """Get the health status of a Docker container."""
    try:
        client = docker.DockerClient(base_url="unix://var/run/docker.sock")
        container = client.containers.get(container_name)
        health = container.attrs["State"].get("Health", {})
        if "Status" in health:
            return health["Status"]
        return container.attrs["State"]["Status"]
    except docker.errors.NotFound:
        logging.error("Container '%s' not found", container_name)
        return "unknown"
    except docker.errors.DockerException as err:
        logging.error("Docker error for '%s': %s", container_name, err)
        return "unknown"


def send_alerts_grouped(service, alerts: List[Dict]) -> None:
    """Send a grouped alert email with container state changes."""
    if not alerts:
        return

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"[DOCKER MONITOR {SERVER}] {len(alerts)} container(s) changed state"

    body_lines = [f"State changes detected on server `{SERVER}` as of {now}:", ""]
    for alert in alerts:
        body_lines.append(
            f"- {alert['type']}: `{alert['container']}` is now **{alert['status'].upper()}**"
        )
    body_lines.append("\nPlease check logs or containers as needed.")
    body = "\n".join(body_lines)

    message = MIMEText(body)
    message["to"] = ALERT_EMAIL
    message["from"] = FROM_EMAIL
    message["subject"] = subject

    raw_message = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
    response = service.users().messages().send(userId="me", body=raw_message).execute()

    logging.info("Grouped alert email sent for %d container(s).", len(alerts))
    logging.debug("Gmail API response: %s", response)


def load_statuses() -> Dict:
    """Load container statuses from a local file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def save_statuses(statuses: Dict) -> None:
    """Save container statuses to a local file."""
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(statuses, file, indent=2)


def poll_once(service, last_statuses: Dict) -> Dict:
    """Poll container statuses and return updated values."""
    new_statuses = {}
    alerts = []

    for container in CONTAINER_NAMES:
        status = get_container_health(container)
        logging.debug("Container '%s' status: %s", container, status)

        last_status = last_statuses.get(container)

        if last_status is None:
            if status in UNHEALTHY_STATES:
                alerts.append(
                    {"container": container, "status": status, "type": "ALERT"}
                )
            else:
                logging.info(
                    "Startup: '%s' is healthy (%s), no alert sent.", container, status
                )
        elif status != last_status:
            if status in UNHEALTHY_STATES:
                alerts.append(
                    {"container": container, "status": status, "type": "ALERT"}
                )
            elif last_status in UNHEALTHY_STATES:
                alerts.append(
                    {"container": container, "status": status, "type": "RECOVERY"}
                )
            else:
                alerts.append(
                    {"container": container, "status": status, "type": "STATE CHANGE"}
                )
        else:
            logging.debug("No alert sent: '%s' unchanged (%s)", container, status)

        new_statuses[container] = status

    send_alerts_grouped(service, alerts)
    return new_statuses


def run_monitor() -> None:
    """Run the main monitoring loop."""
    if not CONTAINER_NAMES:
        logging.error("No containers configured in %s", CONFIG_FILE)
        return

    service = authenticate_gmail_service()
    last_statuses = load_statuses()

    while True:
        logging.info("Polling Docker container statuses...")
        last_statuses = poll_once(service, last_statuses)
        save_statuses(last_statuses)

        unhealthy_now = {
            c: s for c, s in last_statuses.items() if s in UNHEALTHY_STATES
        }
        logging.info(
            "Monitoring complete. %d container(s) in unhealthy state.",
            len(unhealthy_now),
        )

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_monitor()
