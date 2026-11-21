# System Health Monitor

A lightweight, portable, containerized System Health Monitoring application built for cloud computing environments. 

The system collects real-time hardware metrics (CPU, RAM, Disk, and System Uptime), records them into a PostgreSQL database, and visualizes them on an automated, pre-provisioned Grafana dashboard.

Developed on Windows, version-controlled with Git/GitHub, and deployed on Ubuntu Linux using Docker Compose.

---

## 1. Project Overview

The **System Health Monitor** consists of three isolated container services running within a custom Docker bridge network:

1. **Collector (`collector`)**: A Python application using `psutil` that samples system metrics every 30 seconds and writes them to PostgreSQL. It runs as an unprivileged, non-root user (`appuser`).
2. **Database (`db`)**: An official PostgreSQL 16 Alpine database with automatic schema verification, health checking, and internal network isolation.
3. **Dashboard (`grafana`)**: A pre-provisioned Grafana instance that automatically connects to PostgreSQL and displays real-time time-series graphs, gauges, and historical tables.

---

## 2. Architecture Diagram

```text
Host / Browser (Windows or Ubuntu VM)
      |
      | Port 3000:3000 (Only Grafana is exposed to the host)
      v
+-------------------------------------------------------------------+
|               Docker Bridge Network: monitor-net                  |
|                                                                   |
|   +-----------------------+           +-----------------------+   |
|   |   health-collector    | --------> |       health-db       |   |
|   |  (Python 3.11-slim)   |  Inserts  |  (PostgreSQL 16 Alp)  |   |
|   |     User: appuser     |  Metrics  |   Healthcheck enabled |   |
|   +-----------------------+           +-----------------------+   |
|                                                   ^               |
|                                                   | Queries       |
|                                                   | Data          |
|                                       +-----------------------+   |
|                                       |    health-grafana     |   |
|                                       | (Auto-provisioned DB) |   |
|                                       +-----------------------+   |
+-------------------------------------------------------------------+
            |                                       |
            v                                       v
   [postgres_data volume]                  [grafana_data volume]
```

---

## 3. Technologies Used

- **Python 3.11 & `psutil`**: System metrics sampling and telemetry.
- **`psycopg2-binary`**: PostgreSQL database driver with parameterized queries.
- **PostgreSQL 16 Alpine**: Relational time-series storage.
- **Grafana (OSS)**: Visual metrics dashboards with automatic provisioning.
- **Docker & Docker Compose**: Container build, networking, and orchestration.

---

## 4. Project Directory Structure

```text
.
├── .dockerignore                            # Excludes cache, git, and .env from Docker builds
├── .env.example                             # Environment variable template
├── .gitattributes                           # Enforces Linux LF line endings across OSs
├── .gitignore                               # Prevents committing secrets and caches
├── docker-compose.yml                       # Multi-container orchestration specification
├── README.md                                # Comprehensive documentation
├── collector/
│   ├── Dockerfile                           # Container definition for collector (non-root)
│   ├── database.py                          # PostgreSQL connection, schema, and queries
│   ├── health_check.py                      # Metrics collector and monitoring loop
│   └── requirements.txt                     # Pinned Python dependencies
└── grafana/
    ├── dashboards/
    │   └── system-health.json               # Pre-configured dashboard layout
    └── provisioning/
        ├── dashboards/
        │   └── dashboard.yml                # Automatic dashboard loader config
        └── datasources/
            └── datasource.yml               # Automatic PostgreSQL datasource config
```

---

## 5. System Requirements

- **Development OS**: Windows 10/11 or Linux.
- **Deployment OS**: Ubuntu 22.04 LTS / 24.04 LTS (e.g., inside VirtualBox).
- **Installed Software on Ubuntu**:
  - `git`
  - `docker` (v24.0+)
  - `docker-compose-v2` (`docker compose` plugin)

To install Docker on Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
newgrp docker
```

---

## 6. How to Configure `.env`

The project uses environment variables for secure database credentials. Sensitive files like `.env` are strictly excluded from Git.

1. Copy the example configuration to create your local `.env` file:
   ```bash
   cp .env.example .env
   ```

2. *(Optional)* Inspect or customize credentials in `.env`:
   ```env
   POSTGRES_DB=health_monitor
   POSTGRES_USER=monitor_user
   POSTGRES_PASSWORD=change_this_to_a_secure_password
   COLLECTION_INTERVAL=30
   GF_SECURITY_ADMIN_USER=admin
   GF_SECURITY_ADMIN_PASSWORD=admin
   ```

---

## 7. How to Build and Start the Application

### Step 1: Validate Compose Configuration
Before starting, verify the configuration syntax and environment variable substitution:
```bash
docker compose config
```

### Step 2: Build and Start Containers
Build the Python collector image and start all three containers in detached mode:
```bash
docker compose up -d --build
```

### Step 3: Check Container Status and Health
Verify that all services are running and the database is healthy:
```bash
docker compose ps
```
You should see:
- `health-db`: Status `Up (healthy)`
- `health-collector`: Status `Up`
- `health-grafana`: Status `Up`

---

## 8. How to Check Collector Logs

Monitor the real-time telemetry readings being collected and inserted into the database:
```bash
docker compose logs -f collector
```
Example log output:
```text
[2026-11-20 10:45:00 UTC] [ID:0001] CPU:   4.5% | RAM:  42.1% | Disk:  28.4% | Uptime: 12,450.0s
[2026-11-20 10:45:30 UTC] [ID:0002] CPU:   6.2% | RAM:  42.3% | Disk:  28.4% | Uptime: 12,480.0s
```
*(Press `Ctrl+C` to exit log viewing).*

---

## 9. How to Access Grafana

1. Open your web browser on the host machine.
2. Navigate to:
   ```text
   http://localhost:3000
   ```
   *(If accessing an Ubuntu VM from a Windows host, use the VM's IP address, e.g., `http://192.168.56.101:3000` or configured Port Forwarding `3000` -> `3000`).*
3. Log in with the default credentials:
   - **Username**: `admin`
   - **Password**: `admin`
4. The **System Health Monitor** dashboard is loaded automatically:
   - **CPU Usage (%)**: Real-time line graph.
   - **Memory Usage (%)**: Real-time line graph.
   - **Current Disk Usage**: Gauge meter.
   - **System Uptime**: Formatted time display.
   - **Recent Metrics History**: Tabular log of recent readings.
5. The dashboard auto-refreshes every **30 seconds** in sync with the collector.

---

## 10. How Persistent Volumes Work

Docker containers are ephemeral by default, meaning data inside a container is lost when the container is deleted. To guarantee data safety across container restarts and rebuilds, this project uses **separate persistent named volumes**:

- **`postgres_data`**: Mapped to `/var/lib/postgresql/data` inside `health-db`. Ensures all historical telemetry records remain intact across database container updates.
- **`grafana_data`**: Mapped to `/var/lib/grafana` inside `health-grafana`. Retains user preferences, dashboard edits, and session information.

You can inspect existing volumes with:
```bash
docker volume ls
```

---

## 11. How to Stop the Services

### Stop Containers (Preserve Data)
To stop and remove containers while keeping your collected metrics and Grafana data safely saved in persistent volumes:
```bash
docker compose down
```

### Reset Stack (Erase Data)
If you wish to completely wipe all historical metrics and start with a fresh database:
```bash
docker compose down -v
```
*(The `-v` flag removes the named volumes).*

---

## 12. Security & Verification Checklist

- [x] **No hardcoded secrets**: All credentials read dynamically from `.env`.
- [x] **Git protection**: `.env` is ignored by `.gitignore` and `.dockerignore`.
- [x] **Network isolation**: Port `5432` (PostgreSQL) is internal only; only Grafana port `3000` is exposed.
- [x] **Non-root execution**: Collector container runs as user `appuser`.
- [x] **Cross-platform**: `.gitattributes` enforces standard Linux line endings (`LF`).
