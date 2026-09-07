# Local Linux deployment

This setup runs the application directly on a Linux host with Gunicorn and
systemd. It uses a dedicated, unprivileged account and does not require Docker.

## 1. Install system packages

On Ubuntu or Debian:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip rsync
```

Install and configure PostgreSQL separately when it is preferred over the
default SQLite database.

## 2. Install the application

```bash
sudo useradd --system --home /opt/icmrva --shell /usr/sbin/nologin icmrva
sudo mkdir -p /opt/icmrva /etc/icmrva
sudo rsync -a --exclude .git --exclude .env --exclude .venv --exclude instance/ ./ /opt/icmrva/
sudo python3 -m venv /opt/icmrva/.venv
sudo /opt/icmrva/.venv/bin/pip install --upgrade pip
sudo /opt/icmrva/.venv/bin/pip install -r /opt/icmrva/requirements.txt
sudo mkdir -p /opt/icmrva/instance/uploads /opt/icmrva/instance/exports
sudo chown -R root:root /opt/icmrva
sudo chown -R icmrva:icmrva /opt/icmrva/instance
```

Application code remains root-owned. The service can write only inside the
`instance` directory.

## 3. Configure secrets

```bash
sudo cp /opt/icmrva/.env.template /etc/icmrva/icmrva.env
sudo chown root:icmrva /etc/icmrva/icmrva.env
sudo chmod 640 /etc/icmrva/icmrva.env
sudoedit /etc/icmrva/icmrva.env
```

Generate a secret with `openssl rand -hex 32` and place it in `SECRET_KEY`.
Keep `FLASK_DEBUG=0`. Set `SESSION_COOKIE_SECURE=1` when the site is served over
HTTPS. `SESSION_TIMEOUT_HOURS=8` gives authenticated sessions an eight-hour
inactivity timeout. Gunicorn listens on `127.0.0.1:8000` by default.

## 4. Initialize or upgrade the database

```bash
sudo -u icmrva /bin/sh -c 'set -a; . /etc/icmrva/icmrva.env; set +a; cd /opt/icmrva && .venv/bin/flask db upgrade'
```

Create the first administrator interactively:

```bash
sudo -u icmrva /bin/sh -c 'set -a; . /etc/icmrva/icmrva.env; set +a; cd /opt/icmrva && .venv/bin/flask create-admin'
```

## 5. Install the system service

```bash
sudo cp /opt/icmrva/deploy/icmrva.service.example /etc/systemd/system/icmrva.service
sudo systemctl daemon-reload
sudo systemctl enable --now icmrva.service
sudo systemctl status icmrva.service
curl --fail http://127.0.0.1:8000/health
```

View application logs with:

```bash
sudo journalctl -u icmrva.service -f
```

## 6. HTTPS access under a URL path

Keep Gunicorn bound to `127.0.0.1`. For deployment at
`https://minerva.causeofdeathindia.com/icmrva/`, set
`APPLICATION_ROOT=/icmrva` and `SESSION_COOKIE_SECURE=1` in
`/etc/icmrva/icmrva.env`. Add these locations to the existing HTTPS Nginx
server block for `minerva.causeofdeathindia.com`:

```nginx
location = /icmrva {
    return 301 /icmrva/;
}

location /icmrva/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /icmrva;
    proxy_connect_timeout 10s;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
    client_max_body_size 20m;
}
```

The trailing slash on `proxy_pass` is required: Nginx removes `/icmrva/`
before forwarding the request, while `X-Forwarded-Prefix` tells Flask to add
the prefix to generated URLs and the session-cookie path.

## Updating the application

Stop the service, replace the application files while preserving
`/opt/icmrva/instance` and `/etc/icmrva/icmrva.env`, reinstall requirements,
run the database upgrade, and restart:

```bash
sudo systemctl stop icmrva.service
sudo /opt/icmrva/.venv/bin/pip install -r /opt/icmrva/requirements.txt
sudo -u icmrva /bin/sh -c 'set -a; . /etc/icmrva/icmrva.env; set +a; cd /opt/icmrva && .venv/bin/flask db upgrade'
sudo systemctl start icmrva.service
curl --fail http://127.0.0.1:8000/health
```

Local static files, including CSS, are served with a one-hour public cache.
Authenticated HTML and generated workbooks do not receive that cache policy.
