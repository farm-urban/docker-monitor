# 🚨 Container Monitor

Monitor Docker containers by name and receive Gmail alerts when container health or state changes.

This is a self-contained monitoring solution packaged as a Docker container. It requires no changes to the existing containers being monitored.

---

## 📦 Features

- Monitors container health
- Sends grouped email alerts via Gmail API (service account based)
- Configurable poll interval
- Lightweight and portable

---

## 🧱 Requirements

- Docker Engine installed
- Gmail service account with domain-wide delegation
- Containers must have healthchecks or stable state transitions (running/exited/etc.)

---

## 🚀 Quick Start

### 1. Clone and configure:

```bash
git clone https://github.com/your-org/docker-monitor.git
cd docker-monitor
```

### 2. Create your `config.yaml`:

Copy `config.yaml.template` to `config.yaml`.

```yaml
server: "your-server-name"
containers:
  - nginx
  - vaultwarden
alert_email: "you@yourdomain.com"
from_email: "you@yourdomain.com"
delegated_user: "you@yourdomain.com"
poll_interval: 300
```

### 3. Google Email Setup

1.  Create new project in Admin console
2.  Goto "Enabled APIs and services" -> "+Enable API and services"
3.  Enable Gmail API
4.  Create credentials
    - Application data
    - Create service account
    - Click "Done" (no permissions required)
5.  Edit service account
    - Keys -> Add Key -> Create new Key
    - Download the key file as service_account.json into the docker-monitor directory and chmod to 600
    - Details - get Client Id
6.  Add domain wide delegation
    - https://admin.google.com/ac/owl/domainwidedelegation
    - add Client Id from 5

---

### 4. Start the container

```bash
./start.sh
```

---

## ⚙️ Configuration Options

All config is read from `config.yaml`.

---

## 🛠️ Development

Run locally with `./run_dev.sh`

To test within the container, make edits to `monitor_and_alert.py` and rebuild:

```bash
docker compose build
docker compose up
```

---
