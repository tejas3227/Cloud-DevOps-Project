# Docker Production Readiness – Implementation Notes

## Project Overview

**Application:** Python Flask + MariaDB Registration Application  
**Operating System:** CentOS 10 Linux  
**Containerization:** Docker and Docker Compose  
**Application Server:** Gunicorn  
**Database:** MariaDB 10.11  
**Image Security Scanner:** Trivy  

### Application Architecture

```text
              User / Browser
                    |
                    | HTTP :8000
                    |
                    v
          Flask Application Container
               Gunicorn Server
                    |
                    | Docker Network
                    |
                    v
             MariaDB Container
                    |
                    v
             Docker Named Volume
                mariadb_data
```

---

# 1. Docker Networking Security

## What we implemented

We created a custom Docker bridge network for communication between the Flask application and MariaDB.

Configuration in `docker-compose.yml`:

```yaml
networks:
  app-network:
    driver: bridge
```

Both services are connected to this network:

```yaml
services:
  app:
    networks:
      - app-network

  mariadb:
    networks:
      - app-network
```

## Why did we implement this?

- Allows containers to communicate with each other.
- Provides service-name-based DNS resolution.
- Flask connects to MariaDB using the hostname `mariadb`.
- Keeps database communication within the Docker network.

Database configuration:

```yaml
environment:
  DB_HOST: mariadb
  DB_PORT: "3306"
```

## Important observation

MariaDB does not publish its port to the host.

In `docker compose ps`, its port appears as:

```text
3306/tcp
```

The Flask application publishes:

```yaml
ports:
  - "8000:8000"
```

This makes the application accessible through the host's port 8000.

**Skipped:** Restricting the Flask port binding to localhost (`127.0.0.1:8000:8000`).

---

# 2. Docker Image Security

## 2.1 Run the application as a non-root user

In the Dockerfile:

```dockerfile
RUN useradd --create-home appuser && chown -R appuser:appuser /app

USER appuser
```

### Why?

By default, containers can run as root.

Running the application as a non-root user reduces the impact of a potential application compromise.

We created a dedicated user named `appuser` and configured the application to run under that user.

## 2.2 Read-only container filesystem

In Docker Compose:

```yaml
read_only: true
```

### Why?

Prevents processes inside the container from modifying the container's root filesystem.

This reduces the possibility of unauthorized changes to application files or system files.

However, applications may still require writable temporary directories.

## 2.3 Temporary writable storage

Configuration:

```yaml
tmpfs:
  - /tmp:size=64M,mode=1777
```

### Why?

The root filesystem is read-only, but some Python libraries or application processes may require temporary storage.

We provide a temporary writable `/tmp` directory.

- Maximum size: 64 MB
- Permission mode: 1777
- Data is temporary and does not persist after container removal.

## 2.4 Prevent privilege escalation

Configuration:

```yaml
security_opt:
  - no-new-privileges:true
```

### Why?

Prevents processes inside the container from gaining additional privileges through mechanisms such as setuid or setgid executables.

## 2.5 Drop Linux capabilities

Configuration:

```yaml
cap_drop:
  - ALL
```

### Why?

Linux capabilities provide specific privileges that would otherwise be associated with root.

Dropping all capabilities follows the principle of least privilege.

## 2.6 Resource limits

We configured CPU and memory limits for the application container.

### Why?

- Prevents the application from consuming unlimited host resources.
- Helps protect other containers from resource exhaustion.
- Provides predictable resource allocation.

---

# 3. Docker Secrets Management

## Problem with environment variables

Passing passwords directly through environment variables can expose sensitive information through container inspection, process environments, or configuration files.

Instead, we used Docker Compose secrets.

## Secrets directory

```text
project/
│
├── secrets/
│   ├── db_password.txt
│   ├── db_root_password.txt
│   └── flask_secret_key.txt
```

We configured file permissions to restrict access:

```bash
chmod 600 secrets/*.txt
```

## Docker Compose configuration

```yaml
services:
  app:
    secrets:
      - db_password
      - flask_secret_key

  mariadb:
    secrets:
      - db_password
      - db_root_password

secrets:
  db_password:
    file: ./secrets/db_password.txt

  db_root_password:
    file: ./secrets/db_root_password.txt

  flask_secret_key:
    file: ./secrets/flask_secret_key.txt
```

## How does it work?

Docker mounts the secret files inside the relevant containers under:

```text
/run/secrets/
```

Flask receives:

```text
/run/secrets/db_password
/run/secrets/flask_secret_key
```

MariaDB receives:

```text
/run/secrets/db_password
/run/secrets/db_root_password
```

## Flask secret-loading implementation

```python
SECRET_KEY_FILE = os.getenv("SECRET_KEY_FILE")

if SECRET_KEY_FILE:
    with open(SECRET_KEY_FILE, "r") as secret_file:
        SECRET_KEY = secret_file.read().strip()
else:
    SECRET_KEY = os.getenv("SECRET_KEY")
```

## Database password-loading implementation

```python
DB_PASSWORD_FILE = os.getenv("DB_PASSWORD_FILE")

if DB_PASSWORD_FILE:
    with open(DB_PASSWORD_FILE, "r") as secret_file:
        DB_PASSWORD = secret_file.read().strip()
else:
    DB_PASSWORD = os.getenv("DB_PASSWORD")
```

### Important learning

MariaDB's `MARIADB_ROOT_PASSWORD_FILE` and `MARIADB_PASSWORD_FILE` variables are primarily used during initial database initialization.

Changing a secret file does not automatically rotate passwords in an already initialized MariaDB volume.

**Important:** Never delete the existing `mariadb_data` volume just to change a database password.

---

# 4. Docker Logging Configuration

We configured logging for both Flask and MariaDB containers.

Docker Compose:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### Why?

Without log rotation, container logs can consume significant disk space over time.

Our configuration:

- Uses the JSON file logging driver.
- Maximum log file size: 10 MB.
- Keeps up to 3 log files.

## Gunicorn logging

Dockerfile:

```dockerfile
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "app:app"]
```

### Important options

| Option | Purpose |
|---|---|
| `--workers 2` | Runs two Gunicorn worker processes |
| `--bind 0.0.0.0:8000` | Listens on port 8000 on all container interfaces |
| `--access-logfile -` | Sends access logs to stdout |
| `--error-logfile -` | Sends error logs to stderr |
| `--capture-output` | Captures application stdout/stderr |

## Useful logging commands

View application logs:

```bash
docker logs person-registration-app
```

Follow application logs:

```bash
docker logs -f person-registration-app
```

View MariaDB logs:

```bash
docker logs person-registration-db
```

View recent logs:

```bash
docker logs --tail 50 person-registration-app
```

---

# 5. Docker Restart Policy

We configured:

```yaml
restart: unless-stopped
```

### Why?

Automatically restarts a container when its main process exits unexpectedly, unless it has been explicitly stopped.

## Available restart policies

| Policy | Behaviour |
|---|---|
| `no` | Never automatically restart |
| `on-failure` | Restart after a non-zero exit |
| `always` | Always restart after termination |
| `unless-stopped` | Restart unless explicitly stopped |

## How we tested it

First, we checked the configured policy:

```bash
docker inspect person-registration-app \
  --format 'Restart Policy: {{.HostConfig.RestartPolicy.Name}}'
```

Output:

```text
Restart Policy: unless-stopped
```

We then terminated Gunicorn's main process:

```bash
docker exec person-registration-app sh -c 'kill 1'
```

After waiting, we checked:

```bash
docker inspect person-registration-app \
  --format 'Status={{.State.Status}} RestartCount={{.RestartCount}}'
```

Observed result:

```text
Status=running RestartCount=1
```

### Conclusion

Docker successfully restarted the application container after its main process exited.

**Note:** An earlier `docker kill` test produced exit code 137 and did not restart the container. The exact reason for that result was not established.

---

# 6. Docker Image Security Scanning – Trivy

## What is Trivy?

Trivy is a vulnerability scanner that can inspect:

- Operating system packages.
- Application dependencies.
- Container images.
- Secrets and other security issues.

We installed Trivy on CentOS 10 and used it to scan our Docker images.

## Scan the application image

```bash
trivy image --severity HIGH,CRITICAL person-registration-app:v1
```

After making the Dockerfile package-update change, we built and scanned v2:

```bash
trivy image --severity HIGH,CRITICAL person-registration-app:v2
```

## Dockerfile package update

We added:

```dockerfile
RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
```

### Why?

- Refreshes Debian package metadata.
- Installs available package upgrades during the image build.
- Removes downloaded package lists to reduce leftover build data.

## Scan findings

| Finding | Result |
|---|---:|
| HIGH vulnerabilities | 45 |
| CRITICAL vulnerabilities | 0 |
| Python dependency vulnerabilities | 0 |
| OS vulnerabilities | 45 |

The same findings were reported in both v1 and v2.

### Why did the findings remain?

The available package upgrade did not update the affected OS packages.

We also pulled the latest available base image:

```bash
docker pull python:3.12-slim
```

Docker reported:

```text
Status: Image is up to date for python:3.12-slim
```

The base image ID remained unchanged.

### Important learning

Updating packages during a Docker build does not guarantee that every vulnerability will be fixed.

A vulnerability may remain because:

- No patched package is available in the configured repository.
- The vulnerability is marked as deferred.
- The package maintainer has not released a fix.
- The scanner identifies a vulnerability that requires further investigation.

### Current security assessment

- No CRITICAL findings were reported.
- Python dependency scanning reported zero vulnerabilities.
- 45 HIGH OS-package findings remain.
- These findings should be documented and reviewed before production deployment.

Do not claim the image is vulnerability-free.

---

# 7. Development vs Production Configuration

## Existing environment configuration

Our `.env` file:

```env
APP_ENV=development
DB_HOST=localhost
DB_USER=person_app
DB_NAME=person_registration
```

Docker Compose overrides the application environment:

```yaml
environment:
  DB_HOST: mariadb
  DB_PORT: "3306"
  DB_USER: ${DB_USER:?Set this in .env}
  DB_NAME: ${DB_NAME:?Set this in .env}
  DB_PASSWORD_FILE: /run/secrets/db_password
  SECRET_KEY_FILE: /run/secrets/flask_secret_key
  APP_ENV: production
```

## Why are the values different?

When running Flask directly on the host, the database hostname can be:

```text
localhost
```

When Flask runs inside Docker Compose, the database hostname must be:

```text
mariadb
```

This is because Docker Compose provides service-name DNS resolution inside the custom Docker network.

## APP_ENV validation in Flask

```python
APP_ENV = os.getenv("APP_ENV", "development").lower()

if APP_ENV not in ("development", "production"):
    raise RuntimeError("APP_ENV must be development or production")
```

This prevents unsupported environment values.

## Debug mode configuration

We added:

```python
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["DEBUG"] = (APP_ENV == "development")
```

### Behaviour

| Environment | APP_ENV | DEBUG |
|---|---|---|
| Development | development | True |
| Production | production | False |

### Why?

Debug mode provides useful debugging information during development.

However, it should never be enabled in production because it can expose sensitive information.

Our Docker Compose explicitly sets:

```yaml
APP_ENV: production
```

Therefore, Flask debug mode is disabled inside the production-style container.

---

# 8. Application Health Checks

We implemented two health endpoints in Flask.

## 8.1 Liveness endpoint

```python
@app.route("/health/live", methods=["GET"])
def health_live():
    return jsonify({
        "status": "alive"
    }), 200
```

### Purpose

Checks whether the Flask application process is alive and responding.

It does not check the database.

Test:

```bash
curl -i http://localhost:8000/health/live
```

Expected response:

```json
{
  "status": "alive"
}
```

HTTP status:

```text
200 OK
```

## 8.2 Readiness endpoint

```python
@app.route("/health/ready", methods=["GET"])
def health_ready():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()

        return jsonify({
            "status": "ready",
            "database": "connected"
        }), 200

    except mysql.connector.Error:
        app.logger.exception("Readiness check failed")

        return jsonify({
            "status": "not_ready"
        }), 503

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
```

### Purpose

Checks whether the application can connect to the database and execute a simple query.

If the database is unavailable, the endpoint returns HTTP 503.

Test:

```bash
curl -i http://localhost:8000/health/ready
```

Expected healthy response:

```json
{
  "database": "connected",
  "status": "ready"
}
```

HTTP status:

```text
200 OK
```

---

# 9. Final Failure Scenario Testing

We performed practical failure tests to validate application behaviour.

## Test 1 – Application process failure

Command:

```bash
docker exec person-registration-app sh -c 'kill 1'
```

We terminated the main Gunicorn process.

Observed result:

```text
Status=running
RestartCount=1
```

**Result:** PASS

Docker restarted the Flask application container.

## Test 2 – Database failure

We stopped only the MariaDB service:

```bash
docker compose stop mariadb
```

Then tested liveness:

```bash
curl -i http://localhost:8000/health/live
```

Observed:

```text
HTTP/1.1 200 OK
```

Then tested readiness:

```bash
curl -i http://localhost:8000/health/ready
```

Observed:

```text
HTTP/1.1 503 SERVICE UNAVAILABLE
```

Response:

```json
{
  "status": "not_ready"
}
```

**Result:** PASS

Flask remained running even though MariaDB was unavailable.

## Test 3 – Database recovery

We started MariaDB again:

```bash
docker compose start mariadb
```

Checked container status:

```bash
docker compose ps
```

MariaDB returned to:

```text
Up (healthy)
```

Then checked application readiness:

```bash
curl -i http://localhost:8000/health/ready
```

Observed:

```text
HTTP/1.1 200 OK
```

Response:

```json
{
  "database": "connected",
  "status": "ready"
}
```

**Result:** PASS

The application became ready again after database recovery.

## Test 4 – Application functionality

We checked the registration page:

```bash
curl -I http://localhost:8000/
```

Observed:

```text
HTTP/1.1 200 OK
```

We also checked database readiness:

```bash
curl -s http://localhost:8000/health/ready
```

Observed:

```json
{
  "database": "connected",
  "status": "ready"
}
```

**Result:** PASS

The application continued serving requests after the failure and recovery tests.

---

# 10. Useful Docker Commands

## Container management

```bash
docker compose ps
docker compose up -d
docker compose stop
docker compose start
docker compose restart app
docker compose logs -f app
docker compose logs -f mariadb
```

## Inspect container

```bash
docker inspect person-registration-app
```

Check restart policy:

```bash
docker inspect person-registration-app \
  --format '{{.HostConfig.RestartPolicy.Name}}'
```

Check restart count:

```bash
docker inspect person-registration-app \
  --format '{{.RestartCount}}'
```

## Image management

```bash
docker images
docker image inspect person-registration-app:v1
docker image inspect person-registration-app:v2
docker pull python:3.12-slim
```

## Docker network inspection

```bash
docker network ls
docker network inspect 02pythondockerproductiongradeapp_app-network
```

## Volume inspection

```bash
docker volume ls
docker volume inspect 02pythondockerproductiongradeapp_mariadb_data
```

**Warning:** Never run `docker compose down -v` unless you intentionally want to delete the named volumes and understand the data-loss consequences.

---

# 11. Final Project Assessment

## Completed practices

- Custom Docker bridge networking.
- Non-root application execution.
- Read-only application container filesystem.
- Temporary writable filesystem using tmpfs.
- Linux capability restrictions.
- No-new-privileges security setting.
- CPU and memory limits.
- Docker secrets for credentials.
- Persistent MariaDB storage.
- Gunicorn production application server.
- Docker logging configuration and rotation.
- Container restart policy.
- Flask liveness and readiness endpoints.
- Trivy image vulnerability scanning.
- Development and production debug-mode distinction.
- Application failure and recovery testing.
- Database failure and recovery testing.

## Intentionally skipped or still requiring further work

- Restricting Flask's published port to localhost.
- Docker image optimization.
- Resolving or formally assessing the 45 HIGH OS vulnerability findings.
- Further production deployment and infrastructure hardening.

## Final Conclusion

We converted the original Flask and MariaDB Docker application into a more production-oriented containerized application.

The project now demonstrates:

1. Container security and least privilege.
2. Secure handling of application and database secrets.
3. Persistent database storage.
4. Production application serving through Gunicorn.
5. Container logging and restart behaviour.
6. Image vulnerability scanning.
7. Application health monitoring.
8. Failure detection and recovery.

**Important:** This is a production-oriented learning project, not a claim of complete production certification or zero vulnerabilities.

The project provides practical experience with Docker security, container management, application reliability, and troubleshooting.
