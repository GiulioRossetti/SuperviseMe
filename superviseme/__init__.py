import os
import shutil
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from werkzeug.security import generate_password_hash
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

client_processes = {}

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
mail = Mail()


def create_postgresql_db(app):
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "password")
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    dbname = os.getenv("PG_DBNAME", "dashboard")

    app.config[
        "SQLALCHEMY_DATABASE_URI"
    ] = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    app.config["SQLALCHEMY_BINDS"] = {
        "db_admin": f"postgresql://{user}:{password}@{host}:{port}/{dbname}",
    }
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    # is postgresql installed and running?
    try:
        from sqlalchemy import create_engine

        engine = create_engine(
            app.config["SQLALCHEMY_DATABASE_URI"].replace("dashboard", "postgres")
        )
        engine.connect()
    except Exception as e:
        raise RuntimeError(
            "PostgreSQL is not installed or running. Please check your configuration."
        ) from e

    # does dbname exist? if not, create it and load schema
    from sqlalchemy import create_engine
    from sqlalchemy import text
    from werkzeug.security import generate_password_hash

    # Connect to a default admin DB (typically 'postgres') to check for existence of target DBs
    admin_engine = create_engine(
        f"postgresql://{user}:{password}@{host}:{port}/postgres"
    )

    # --- Check and create dashboard DB if needed ---
    with admin_engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'")
        )
        db_exists = result.scalar() is not None

    if not db_exists:
        # Create the database (requires AUTOCOMMIT mode)
        with admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(text(f"CREATE DATABASE {dbname}"))

        # Connect to the new DB and load schema
        dashboard_engine = create_engine(app.config["SQLALCHEMY_BINDS"]["db_admin"])
        with dashboard_engine.connect() as db_conn:
            # Load SQL schema
            schema_sql = open(
                f"{BASE_DIR}{os.sep}..{os.sep}data_schema{os.sep}postgre_dashboard.sql",
                "r",
            ).read()
            db_conn.execute(text(schema_sql))

            # Generate hashed password
            hashed_pw = generate_password_hash("test", method="pbkdf2:sha256")

            # Insert initial admin user
            db_conn.execute(
                text(
                    """
                     INSERT INTO user_mgmt (username, email, password, role)
                     VALUES (:username, :email, :password, :role)
                     """
                ),
                {
                    "username": "admin",
                    "email": "admin@ysocial.com",
                    "password": hashed_pw,
                    "role": "admin",
                },
            )

        dashboard_engine.dispose()

    # --- Check and create dummy DB if needed ---
    with admin_engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'")
        )
        dummy_exists = result.scalar() is not None

    if not dummy_exists:
        with admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(text(f"CREATE DATABASE {dbname}"))

        dummy_engine = create_engine(app.config["SQLALCHEMY_BINDS"]["db_exp"])
        with dummy_engine.connect() as dummy_conn:
            schema_sql = open(
                f"{BASE_DIR}{os.sep}..{os.sep}data_schema{os.sep}postgre_server.sql",
                "r",
            ).read()
            dummy_conn.execute(text(schema_sql))

            # Generate hashed password
            hashed_pw = generate_password_hash("test", method="pbkdf2:sha256")

            # Insert initial admin user
            stmt = text("""
                        INSERT INTO user_mgmt (username, email, password, user_type, joined_on)
                        VALUES (:username, :email, :password, :user_type, :joined_on)
                        """)

            dummy_conn.execute(
                stmt,
                {
                    "username": "admin",
                    "email": "admin@ysocial.com",
                    "password": hashed_pw,
                    "user_type": "admin",
                    "joined_on": 0,
                }
            )

        dummy_engine.dispose()

    admin_engine.dispose()


def create_app(db_type="sqlite"):
    app = Flask(__name__, static_url_path="/static")

    # Copy databases if missing (keep your existing logic)
    if not os.path.exists(f"{BASE_DIR}{os.sep}db{os.sep}dashboard.db"):
        shutil.copyfile(
            f"{BASE_DIR}{os.sep}..{os.sep}data_schema{os.sep}database_dashboard.db",
            f"{BASE_DIR}{os.sep}db{os.sep}dashboard.db",
        )

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "4323432nldsf")
    
    # Mail configuration
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "localhost")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", "noreply@superviseme.local")

    if db_type == "sqlite":
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR}/db/dashboard.db"
        app.config["SQLALCHEMY_BINDS"] = {
            "db_admin": f"sqlite:///{BASE_DIR}/db/dashboard.db",
       #     "db_exp": f"sqlite:///{BASE_DIR}/db/dummy.db",
        }
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False}
        }

    elif db_type == "postgresql":
        create_postgresql_db(app)
    else:
        raise ValueError("Unsupported db_type, use 'sqlite' or 'postgresql'")

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    from .models import User_mgmt

    # insert the admin user if it doesn't exist
    with app.app_context():
        #db.create_all()  # Create tables if they don't exist

        # Check if the admin user exists
        admin_user = User_mgmt.query.filter_by(username="admin").first()
        if not admin_user:
            hashed_pw = generate_password_hash("test", method="pbkdf2:sha256")
            new_admin = User_mgmt(
                username="admin",
                name="Dr.",
                surname="God",
                email="admin@supervise.me",
                password=hashed_pw,
                user_type="admin",
                joined_on=int(time.time()),

            )
            db.session.add(new_admin)
            db.session.commit()

    @login_manager.user_loader
    def load_user(user_id):
        print(f"Loading user with ID: {user_id}")
        return User_mgmt.query.get(int(user_id))

    # Register your blueprints here as before
    from superviseme.routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from superviseme.routes.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint)

    from superviseme.routes.student import student as student_blueprint
    app.register_blueprint(student_blueprint)

    from superviseme.routes.supervisor import supervisor as supervisor_blueprint
    app.register_blueprint(supervisor_blueprint)

    from superviseme.routes.profile import profile as profile_blueprint
    app.register_blueprint(profile_blueprint)

    from superviseme.routes.notifications import notifications as notifications_blueprint
    app.register_blueprint(notifications_blueprint)

    # Initialize the task scheduler for background jobs
    from superviseme.utils.task_scheduler import init_scheduler
    init_scheduler(app)

    # Register template filters
    @app.template_filter('format_todo_links')
    def format_todo_links_filter(text, user_type='supervisor'):
        from superviseme.utils.todo_parser import format_text_with_todo_links
        base_url = f"/{user_type}/" if user_type else "/"
        return format_text_with_todo_links(text, base_url)

    return app
