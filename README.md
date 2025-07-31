Script to send alerts when containers aren't healthy

**NB:** Useful alias for checking ps:

`alias docker-ps=docker container ls --format "table {{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Status}}"`

## Python infrastructure

```
sudo apt-get install  python3-venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib pyaml
```

## Systemd:

Edit `docker-monitor.service` to set location of directory if not `/opt/docker-monitor`

```
sudo cp docker-monitor.service  /etc/systemd/system/docker-monitor.service
sudo cp docker-monitor.timer /etc/systemd/system/docker-monitor.timer

sudo systemctl daemon-reexec
sudo systemctl daemon-reload

sudo systemctl enable docker-monitor.timer
sudo systemctl start docker-monitor.timer
```

## On google workspace

1.  Create new project in Admin console
2.  Goto "Enabled APIs and services" -> "+Enable API and services"
3.  Enable Gmail API
4.  Create credentials
    - Application data
    - Create service account
    - Click "Done" (no permissions required)
5.  Edit service account
    - Keys -> Add Key -> Create new Key
    - Download the key file as service_account.json
    - Details - get Client Id
6.  Add domain wide delegation
    - https://admin.google.com/ac/owl/domainwidedelegation
    - add Client Id from 5
7. change mode of service_account.json to 600
