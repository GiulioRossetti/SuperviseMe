# SuperviseMe Docker Setup

This document describes how to run SuperviseMe using Docker with a complete production-ready setup including reverse proxy, database persistence, and mail server.

## Architecture

The Docker setup includes the following services:

- **superviseme_app**: Flask application running with Gunicorn
- **postgres**: PostgreSQL database with persistent storage
- **nginx**: Reverse proxy with SSL termination and static file serving
- **mailhog**: Development mail server for testing email functionality

## Quick Start

1. **Clone and navigate to the repository**:
   ```bash
   git clone https://github.com/GiulioRossetti/SuperviseMe.git
   cd SuperviseMe
   ```

2. **Create environment configuration**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and customize the values, especially:
   - `SECRET_KEY`: Use a strong, unique secret key
   - `PG_PASSWORD`: Set a secure database password

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Main application: https://localhost (accept self-signed certificate)
   - Mail server UI: http://localhost:8025

## Services Details

### Web Application (superviseme_app)
- **Port**: Internal 8080 (proxied through Nginx)
- **Technology**: Flask + Gunicorn WSGI server
- **Database**: PostgreSQL with automatic schema initialization
- **Health Check**: HTTP health endpoint
- **Volumes**: Application data persistence

### Database (postgres)
- **Port**: Internal 5432
- **Technology**: PostgreSQL 15 Alpine
- **Persistence**: Named volume `postgres_data`
- **Initialization**: Automatic database and schema creation
- **Health Check**: PostgreSQL ready check

### Reverse Proxy (nginx)
- **Ports**: 80 (HTTP → HTTPS redirect), 443 (HTTPS)
- **Features**: 
  - SSL termination with self-signed certificates
  - Static file serving and caching
  - Rate limiting for security
  - Security headers
  - Gzip compression
- **Health Check**: HTTP health endpoint

### Mail Server (mailhog)
- **Ports**: 8025 (Web UI), 1025 (SMTP)
- **Purpose**: Development mail server for testing notifications
- **Features**: Web interface to view sent emails

## Configuration

### Environment Variables

Key environment variables (see `.env.example`):

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key
DEBUG=false

# Database Configuration  
PG_USER=superviseme_user
PG_PASSWORD=your-secure-password
PG_DBNAME=superviseme

# Mail Configuration
MAIL_DEFAULT_SENDER=noreply@superviseme.local
MAIL_SERVER=mailhog
MAIL_PORT=1025
```

### SSL Certificates

For development, self-signed certificates are automatically generated. For production:

1. Replace certificates in `nginx/ssl/` directory:
   - `superviseme.crt` - SSL certificate
   - `superviseme.key` - Private key

2. Update `nginx/nginx.conf` server_name to match your domain

## Development Mode

For development with hot reloading:

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Development features:
- Flask development server with auto-reload
- Source code volume mounting
- Debug mode enabled
- Direct access to application on port 8080

## Data Persistence

### Database Data
- **Volume**: `postgres_data`
- **Location**: PostgreSQL data directory
- **Backup**: Use `pg_dump` through the container:
  ```bash
  docker-compose exec postgres pg_dump -U superviseme_user superviseme > backup.sql
  ```

### Application Data
- **Volume**: `app_data`  
- **Location**: Application database files and uploads
- **Purpose**: Persistent storage for SQLite fallback and file uploads

## Monitoring and Health Checks

All services include health checks:

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f superviseme_app
docker-compose logs -f postgres
docker-compose logs -f nginx

# Check health status
docker-compose exec superviseme_app curl -f http://localhost:8080/
```

## Email Testing

The MailHog service provides a complete email testing environment:

1. **Access Web Interface**: http://localhost:8025
2. **SMTP Server**: `mailhog:1025` (internal) 
3. **Send Test Email**: Use the admin panel notification settings
4. **View Emails**: All sent emails appear in the MailHog web interface

## Security Considerations

### Development
- Self-signed SSL certificates (browser will show warnings)
- Default credentials should be changed
- MailHog is for development only

### Production
- Replace self-signed certificates with valid SSL certificates
- Change all default passwords and secret keys
- Use a production mail server (SMTP)
- Configure firewall rules
- Enable log monitoring and alerting
- Regular security updates

## Scaling and Production Deployment

### Production Checklist
- [ ] Replace self-signed SSL certificates
- [ ] Set strong SECRET_KEY and database passwords
- [ ] Configure production mail server
- [ ] Set up external database backup
- [ ] Configure log aggregation
- [ ] Set up monitoring and alerting
- [ ] Configure reverse proxy caching
- [ ] Set resource limits in docker-compose.yml

### Scaling
For high availability:
1. Use multiple app container instances
2. External database (managed PostgreSQL)
3. Load balancer (HAProxy/AWS ALB)
4. Redis for session storage
5. External file storage (S3/GCS)

## Troubleshooting

### Common Issues

1. **Database Connection Failed**:
   ```bash
   # Check PostgreSQL logs
   docker-compose logs postgres
   
   # Verify connection
   docker-compose exec postgres pg_isready -U superviseme_user
   ```

2. **SSL Certificate Errors**:
   ```bash
   # Regenerate self-signed certificates
   cd nginx/ssl
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout superviseme.key -out superviseme.crt \
     -subj "/C=US/ST=Dev/L=Local/O=SuperviseMe/CN=localhost"
   ```

3. **Application Won't Start**:
   ```bash
   # Check application logs
   docker-compose logs superviseme_app
   
   # Check database initialization
   docker-compose exec superviseme_app python seed_database.py
   ```

4. **Nginx Configuration Issues**:
   ```bash
   # Test Nginx configuration
   docker-compose exec nginx nginx -t
   
   # Reload Nginx configuration
   docker-compose exec nginx nginx -s reload
   ```

### Useful Commands

```bash
# Start services
docker-compose up -d

# Stop services  
docker-compose down

# Rebuild and restart
docker-compose up -d --build

# View real-time logs
docker-compose logs -f

# Execute commands in containers
docker-compose exec superviseme_app bash
docker-compose exec postgres psql -U superviseme_user -d superviseme

# Remove all data (destructive!)
docker-compose down -v
```

## Support

For issues and questions:
- Check application logs: `docker-compose logs superviseme_app`
- Verify service health: `docker-compose ps`
- Review this documentation
- Check the main project README.md