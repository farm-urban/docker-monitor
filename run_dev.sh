#!/bin/bash

if [ ! -d venv ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade \
        google-api-python-client \
        google-auth-httplib2 \
        google-auth-oauthlib \
        pyaml \
        docker
fi

venv/bin/python3 monitor_and_alert.py
