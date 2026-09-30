# Local On-Prem Telemetry

The on-prem app writes structured JSON logs to `%ProgramData%\ErrorLens\logs` on Windows. Backend and Streamlit output are written to separate per-process rotating files to avoid rotation races when multiple workers run. The default rotation is 10 MiB per file with 10 backups. Set `ERRORLENS_LOG_DIR`, `ERRORLENS_LOG_MAX_BYTES`, or `ERRORLENS_LOG_BACKUP_COUNT` to override these defaults. The Windows service account must be allowed to create and write files in the log directory.

Grafana Alloy tails those files and sends them only to the local Loki container. Grafana is bound to localhost on port 3000; Loki is not published to the host network. Loki retains logs for 30 days in a Docker volume. The provisioned Grafana dashboard is named **ErrorLens On-Prem Logs**; Grafana Explore is also available for ad hoc LogQL searches.

## Prerequisites

- Python dependencies already listed in the project requirements. Local file logging uses only the Python standard library; no telemetry SDK is needed for on-prem mode.
- Docker Desktop with Docker Compose on Windows, or Docker Engine with the Compose plugin on Linux. Docker is not installed automatically by this repository.
- Public container images for Grafana, Loki, and Grafana Alloy are pulled from Docker Hub when the stack starts.

## Start on Windows

From the repository root in PowerShell:

```powershell
Copy-Item monitoring/.env.example monitoring/.env
notepad monitoring/.env
docker compose --env-file monitoring/.env -f monitoring/compose.yaml up -d
```

Set a unique `GRAFANA_ADMIN_PASSWORD` before starting. Open `http://localhost:3000` and sign in with the local admin username and password from `monitoring/.env`.

Stop the containers while preserving dashboards and Loki data:

```powershell
docker compose --env-file monitoring/.env -f monitoring/compose.yaml down
```

`docker compose down -v` deletes the persisted Grafana and Loki volumes. Back up the Docker volumes if the logs are subject to organizational retention requirements.

If you override `ERRORLENS_LOG_DIR`, set the same absolute host path in the application's environment and `monitoring/.env`. The account running Docker must be able to mount that directory. For a Linux host, use a Linux path such as `/var/log/errorlens` in `monitoring/.env` and grant the application and Docker access to it.

## Accounts and Network

No Azure account, Grafana Cloud account, or external portal account is needed. Grafana uses a local admin account configured in `monitoring/.env`; it is not created in a portal. Docker Desktop may have separate licensing/sign-in requirements under an organization's policy. Public image pulls normally work without a Docker Hub login, subject to Docker Hub rate limits and company network policy.

The containers need outbound access to Docker Hub only to download or update their images. At runtime Alloy, Loki, and Grafana communicate on a private Docker network; this stack does not send logs to Azure or Grafana Cloud. The current configuration is for one host. Do not expose Grafana or Loki to a wider network without adding authentication, TLS, and firewall controls.