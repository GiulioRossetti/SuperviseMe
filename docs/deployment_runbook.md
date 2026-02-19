# Deployment Runbook

This document outlines the procedures for deploying, maintaining, and recovering the SuperviseMe application in a production environment.

## 1. Pre-Deployment Checklist

Before deploying any changes or updates:

-   [ ] **Code Review**: Ensure all code changes have been reviewed and approved.
-   [ ] **Testing**: Run all automated tests (`make test`) and ensure they pass.
-   [ ] **Schema Alignment**: Check for database schema changes (`make schema`).
-   [ ] **Environment Variables**: Verify that all necessary environment variables are set in the `.env` file (or deployment secrets).
-   [ ] **Backup**: Create a backup of the current database.

## 2. Deployment Steps

### 2.1. Initial Deployment

1.  **Clone Repository**:
    ```bash
    git clone https://github.com/GiulioRossetti/SuperviseMe.git
    cd SuperviseMe
    ```

2.  **Configure Environment**:
    -   Copy `.env.example` to `.env`.
    -   Update values for `SECRET_KEY`, `ADMIN_BOOTSTRAP_PASSWORD`, `PG_PASSWORD`, etc.
    -   **Important**: Set `FLASK_ENV=production`.

3.  **Setup SSL**:
    -   Generate or place SSL certificates in `nginx/ssl/`.

4.  **Start Services**:
    ```bash
    docker-compose up -d
    ```

5.  **Initialize Database (if needed)**:
    -   The application will automatically create tables if they don't exist.
    -   Wait for the services to be healthy (`docker-compose ps`).

### 2.2. Updating the Application

1.  **Pull Latest Changes**:
    ```bash
    git pull origin main
    ```

2.  **Rebuild Containers**:
    ```bash
    docker-compose build
    ```

3.  **Apply Updates**:
    ```bash
    docker-compose up -d
    ```
    -   Docker Compose will recreate containers with configuration or image changes.

4.  **Run Migrations**:
    -   If there are database schema changes, run the migration scripts:
        ```bash
        docker-compose exec superviseme_app python migrate_database.py
        docker-compose exec superviseme_app python migrate_telegram.py
        docker-compose exec superviseme_app python migrate_researcher.py
        ```

## 3. Maintenance

### 3.1. Database Backups

-   **Manual Backup**:
    ```bash
    docker-compose exec postgres pg_dump -U superviseme_user superviseme > backup_$(date +%Y%m%d).sql
    ```
-   **Automated Backup**: Schedule a cron job on the host machine to run the backup command daily.

### 3.2. Log Monitoring

-   View logs for all services:
    ```bash
    docker-compose logs -f
    ```
-   View logs for a specific service:
    ```bash
    docker-compose logs -f superviseme_app
    ```

## 4. Disaster Recovery

### 4.1. Restore Database

1.  **Stop Application**:
    ```bash
    docker-compose stop superviseme_app
    ```

2.  **Restore from Backup**:
    ```bash
    cat backup.sql | docker-compose exec -T postgres psql -U superviseme_user -d superviseme
    ```

3.  **Restart Application**:
    ```bash
    docker-compose start superviseme_app
    ```

## 5. Troubleshooting

-   **Service Unhealthy**: Check logs (`docker-compose logs`) for error messages.
-   **Database Connection Error**: Verify `PG_HOST`, `PG_USER`, and `PG_PASSWORD` in `.env`.
-   **Nginx 502 Bad Gateway**: The Flask application might be down or starting up. Check `superviseme_app` logs.
-   **Email Issues**: Check `mailhog` UI or SMTP server logs. Verify `MAIL_SERVER` settings.

## 6. Smoke Tests

After deployment, perform a smoke test to verify basic functionality:

1.  Access the homepage (`https://your-domain.com`).
2.  Log in as an administrator.
3.  Check the "System Status" or dashboard for any alerts.
4.  Send a test email from the Admin Dashboard.
