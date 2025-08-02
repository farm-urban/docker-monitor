# Dockerfile for container-monitor
# Reusable container that monitors other Docker containers via the socket,
# and sends alerts using Gmail API

FROM python:3.11-slim

# Install security updates to reduce vulnerabilities
RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies including Docker SDK
RUN pip install --no-cache-dir \
    google-api-python-client \
    google-auth \
    google-auth-oauthlib \
    pyyaml \
    docker

# Copy in the monitoring script
COPY monitor_and_alert.py ./

# Default command (can be overridden)
CMD ["python", "monitor_and_alert.py"]
