"""
WSGI entry point for SuperviseMe application
"""
import os
from superviseme import create_app

# Use PostgreSQL only when PG_HOST is explicitly configured (Docker / production).
# When PG_HOST is absent (plain local run without Docker) fall back to SQLite so
# that `python wsgi.py` works out of the box without a running PostgreSQL server.
_default_db = "postgresql" if os.getenv("PG_HOST") else "sqlite"
db_type = os.getenv("DB_TYPE", _default_db)

# Create the application instance
app = create_app(db_type=db_type)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)