# Configuration and Settings

SuperviseMe is configured using environment variables. These can be set in a `.env` file in the root directory or as system environment variables.

## General Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `FLASK_ENV` | The Flask environment. Set to `production` for deployment. | `production` | No |
| `SECRET_KEY` | A secret key used for session security. Must be strong and unique in production. | `change-this...` | Yes (in prod) |
| `DEBUG` | Enable Flask debug mode. Set to `false` in production. | `false` | No |
| `ENABLE_SCHEDULER` | Enable the background scheduler for weekly emails. | `true` | No |
| `SKIP_DB_SEED` | Skip database seeding on startup. Recommended `true` for production. | `true` | No |
| `BASE_URL` | The base URL of the application (e.g., `https://superviseme.example.com`). Used for generating absolute links. | `https://superviseme.local` | No |

## Database Configuration

SuperviseMe supports SQLite (default) and PostgreSQL.

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PG_USER` | PostgreSQL username. | `superviseme_user` | No (if using SQLite) |
| `PG_PASSWORD` | PostgreSQL password. | `superviseme_secure_password` | No (if using SQLite) |
| `PG_HOST` | PostgreSQL host. | `postgres` | No (if using SQLite) |
| `PG_PORT` | PostgreSQL port. | `5432` | No (if using SQLite) |
| `PG_DBNAME` | PostgreSQL database name. | `superviseme` | No (if using SQLite) |

## Admin Bootstrap

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ADMIN_BOOTSTRAP_PASSWORD` | The initial password for the `admin` user created on first run. | `change-this...` | Yes |

## Mail Configuration

Required for weekly email reports and notifications.

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MAIL_SERVER` | SMTP server address. | `mailhog` | No |
| `MAIL_PORT` | SMTP server port. | `1025` | No |
| `MAIL_USE_TLS` | Use TLS for connection security. | `false` | No |
| `MAIL_USE_SSL` | Use SSL for connection security. | `false` | No |
| `MAIL_USERNAME` | SMTP username. | - | No |
| `MAIL_PASSWORD` | SMTP password. | - | No |
| `MAIL_DEFAULT_SENDER` | Default sender email address. | `noreply@superviseme.local` | No |

## Social Login Configuration

See [Social Login Setup](social_login.md) for details.

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID. | No (if not using Google login) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret. | No (if not using Google login) |
| `ORCID_CLIENT_ID` | ORCID Client ID. | No (if not using ORCID login) |
| `ORCID_CLIENT_SECRET` | ORCID Client Secret. | No (if not using ORCID login) |

## Telegram Configuration

See [Telegram Setup](telegram_setup.md) for details.

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token. | No (if not using Telegram) |
| `TELEGRAM_BOT_USERNAME` | Telegram Bot Username. | No (if not using Telegram) |

## Seeding Configuration (Optional)

Used by `seed_database.py` to create sample users with specific passwords.

| Variable | Description |
|----------|-------------|
| `SEED_DEFAULT_PASSWORD` | Default password for seeded users. |
| `SEED_SUPERVISOR_PASSWORD` | Password for seeded supervisors. |
| `SEED_STUDENT_PASSWORD` | Password for seeded students. |
| `SEED_RESEARCHER_PASSWORD` | Password for seeded researchers. |
