"""
WSGI entry point for SuperviseMe application
"""
import os
from superviseme import create_app

# Get database type from environment, default to postgresql for production
db_type = os.getenv("DB_TYPE", "postgresql")

# Create the application instance
app = create_app(db_type=db_type)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)