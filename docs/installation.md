# Installation and First Run

This page covers everything needed before the [Configuration](configuration.md) page.

Repository: <https://github.com/GiulioRossetti/SuperviseMe>

## 1. Prerequisites

Choose one setup path:

- Local Python setup:
  - Python 3.8+
  - `pip`
  - (Optional) PostgreSQL if you do not want SQLite
- Docker setup:
  - Docker
  - Docker Compose

## 2. Download the Project

```bash
git clone https://github.com/GiulioRossetti/SuperviseMe.git
cd SuperviseMe
```

## 3. Local Python Setup (without Docker)

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Prepare environment variables:

```bash
cp .env.example .env
```

At minimum, update these in `.env` before first run:

- `SECRET_KEY`
- `ADMIN_BOOTSTRAP_PASSWORD`

## 4. Database Preparation

### New installation (fresh DB)

You can seed demo data (optional):

```bash
python scripts/seed_database.py
```

### Existing installation (already has a DB)

If you are upgrading an existing instance, run migration scripts before starting:

```bash
python scripts/migrate_database.py
python scripts/migrate_telegram.py
python scripts/migrate_researcher.py
```

Optional schema check:

```bash
python scripts/check_schema_alignment.py
```

## 5. Start the Application (Local Python)

```bash
python superviseme.py
```

Open:

- `http://127.0.0.1:8080`

## 6. Docker Quick Start (alternative)

If you prefer Docker:

```bash
cp .env.example .env
docker-compose up -d
```

Then open:

- `https://localhost`
- Mail UI: `http://localhost:8025`

For full Docker details see [Docker Deployment](docker_deployment.md).

## 7. Next Step

After installation is complete, continue with [Configuration](configuration.md).
