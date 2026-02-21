import os
import re
import shutil
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_migrate import Migrate
from authlib.integrations.flask_client import OAuth
from sqlalchemy import MetaData
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, text
import time
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

client_processes = {}

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
login_manager = LoginManager()
login_manager.login_view = "auth.login"
mail = Mail()
csrf = CSRFProtect()
migrate = Migrate()
oauth = OAuth()

INSECURE_SECRET_KEY_VALUES = {
    "",
    "4323432nldsf",
    "change-this-secret-key-in-production-123456789",
    "your-secret-key-change-in-production",
}


def _is_production_environment():
    return os.getenv("FLASK_ENV", "production").lower() == "production"


def _configure_secret_key(app):
    secret_key = os.getenv("SECRET_KEY", "")
    if _is_production_environment() and secret_key in INSECURE_SECRET_KEY_VALUES:
        raise RuntimeError(
            "In production, SECRET_KEY must be set to a strong non-default value."
        )

    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable is not set")
    app.config["SECRET_KEY"] = secret_key


def _validate_postgres_dbname(dbname):
    """
    Keep dbname constrained to safe SQL identifier characters to avoid SQL injection
    when used in CREATE DATABASE.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", dbname or ""):
        raise ValueError(
            "PG_DBNAME must be a valid SQL identifier (letters, digits, underscore; cannot start with digit)."
        )


def create_postgresql_db(app):
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "password")
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    dbname = os.getenv("PG_DBNAME", "dashboard")
    _validate_postgres_dbname(dbname)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    app.config["SQLALCHEMY_BINDS"] = {
        "db_admin": f"postgresql://{user}:{password}@{host}:{port}/{dbname}",
    }
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    admin_uri = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    created_db = False
    admin_engine = create_engine(admin_uri)
    try:
        # Confirm server availability and check target database existence.
        with admin_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": dbname},
            )
            db_exists = result.scalar() is not None

        if not db_exists:
            with admin_engine.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as conn:
                conn.execute(text(f'CREATE DATABASE "{dbname}"'))
            created_db = True
    except Exception as e:
        raise RuntimeError(
            "PostgreSQL is not installed/running or credentials are invalid."
        ) from e
    finally:
        admin_engine.dispose()

    app.config["POSTGRES_DB_CREATED"] = created_db
    return created_db


def _run_db_upgrade(app):
    """
    Run any pending Alembic migrations so the live database schema always
    matches the current model definitions.

    Handles three scenarios:
    1. Fresh database (no tables yet) – migrations create everything from scratch.
    2. Existing database already tracked by Alembic – only pending revisions are applied.
    3. Legacy database (tables exist but no alembic_version tracking) – stamped at
       the baseline revision (0001) first, then upgraded to HEAD.
    """
    from flask_migrate import upgrade as flask_db_upgrade, stamp as flask_db_stamp
    from sqlalchemy import inspect as sa_inspect

    _log = logging.getLogger(__name__)

    with app.app_context():
        try:
            inspector = sa_inspect(db.engine)
            existing_tables = set(inspector.get_table_names())

            # Legacy DB: tables present but Alembic has never tracked this DB.
            # Stamp at the baseline revision so upgrade() only applies deltas.
            if existing_tables and "alembic_version" not in existing_tables:
                _log.info(
                    "Untracked database detected; stamping at baseline revision '0001' "
                    "before upgrading."
                )
                flask_db_stamp(revision="0001")

            flask_db_upgrade()
        except Exception:
            _log.warning(
                "Automatic database schema upgrade failed; the application may "
                "not function correctly if the schema is out of date.",
                exc_info=True,
            )


def _stamp_sqlite_db_head(db_path):
    """
    Ensure a copied SQLite database has an alembic_version record at the
    current head revision, so that 'flask db upgrade' is a no-op on a DB
    that was bootstrapped from the data_schema copy rather than via migrations.
    """
    import sqlite3 as _sqlite3

    _log = logging.getLogger(__name__)
    migrations_dir = os.path.join(BASE_DIR, "..", "migrations")
    head_revision = None
    try:
        from alembic.script import ScriptDirectory
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig()
        cfg.set_main_option("script_location", migrations_dir)
        script = ScriptDirectory.from_config(cfg)
        head_revision = script.get_current_head()
    except ImportError:
        _log.debug("alembic not available; skipping alembic_version stamp")
    except Exception:
        _log.warning("Could not determine Alembic head revision; skipping stamp", exc_info=True)

    if not head_revision:
        return

    conn = _sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(32) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
        existing = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        if not existing:
            conn.execute("INSERT INTO alembic_version VALUES (?)", (head_revision,))
            conn.commit()
    except Exception:
        _log.warning("Failed to stamp alembic_version in bootstrapped DB %s", db_path, exc_info=True)
    finally:
        conn.close()


def create_app(db_type="sqlite", skip_user_init=False):
    load_dotenv(override=False)
    app = Flask(__name__, static_url_path="/static")

    # When Flask-Migrate CLI (flask db ...) invokes the app factory it does not
    # pass skip_user_init=True, so honour the env var as a secondary opt-out.
    if os.getenv("FLASK_SKIP_USER_INIT", "").lower() in ("1", "true", "yes"):
        skip_user_init = True

    # Copy databases if missing (keep your existing logic)
    if not os.path.exists(f"{BASE_DIR}{os.sep}db{os.sep}dashboard.db"):
        if os.path.exists(f"{BASE_DIR}{os.sep}..{os.sep}data_schema{os.sep}database_dashboard.db"):
            shutil.copyfile(
                f"{BASE_DIR}{os.sep}..{os.sep}data_schema{os.sep}database_dashboard.db",
                f"{BASE_DIR}{os.sep}db{os.sep}dashboard.db",
            )
            # Stamp the copied DB with the current Alembic head so that
            # 'flask db upgrade' is a no-op on this bootstrapped database.
            _stamp_sqlite_db_head(f"{BASE_DIR}{os.sep}db{os.sep}dashboard.db")

    _configure_secret_key(app)
    
    # Mail configuration
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "localhost")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", "noreply@superviseme.local")

    if db_type == "sqlite":
        sqlite_uri = os.getenv(
            "SQLALCHEMY_DATABASE_URI",
            f"sqlite:///{BASE_DIR}/db/dashboard.db",
        )
        app.config["SQLALCHEMY_DATABASE_URI"] = sqlite_uri
        app.config["SQLALCHEMY_BINDS"] = {
            "db_admin": sqlite_uri,
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
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)

    # Configure Google OAuth
    oauth.register(
        name='google',
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    # Configure ORCID OAuth
    oauth.register(
        name='orcid',
        client_id=os.getenv("ORCID_CLIENT_ID"),
        client_secret=os.getenv("ORCID_CLIENT_SECRET"),
        access_token_url='https://orcid.org/oauth/token',
        authorize_url='https://orcid.org/oauth/authorize',
        api_base_url='https://pub.orcid.org/v3.0/',
        client_kwargs={'scope': '/read-public'}
    )

    # Ensure the database schema is up to date before any queries are made.
    _run_db_upgrade(app)

    from .models import User_mgmt

    # insert the admin user if it doesn't exist, or keep their password in sync
    # with ADMIN_BOOTSTRAP_PASSWORD so that the value set in .env always works.
    if not skip_user_init:
        with app.app_context():
            # Check if the admin user exists (only if tables exist)
            try:
                bootstrap_password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "")
                admin_user = User_mgmt.query.filter_by(username="admin").first()
                if not admin_user:
                    if not bootstrap_password:
                        app.logger.warning(
                            "Admin user missing but ADMIN_BOOTSTRAP_PASSWORD is not set; skipping bootstrap admin creation."
                        )
                    else:
                        hashed_pw = generate_password_hash(
                            bootstrap_password, method="pbkdf2:sha256"
                        )
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
                elif bootstrap_password and not check_password_hash(
                    admin_user.password, bootstrap_password
                ):
                    # Admin exists but their stored password no longer matches the
                    # configured ADMIN_BOOTSTRAP_PASSWORD – re-sync it so the value
                    # in .env always allows login (useful after password rotations or
                    # a fresh clone with an existing database).
                    admin_user.password = generate_password_hash(
                        bootstrap_password, method="pbkdf2:sha256"
                    )
                    db.session.commit()
                    app.logger.info(
                        "Admin password synchronised with ADMIN_BOOTSTRAP_PASSWORD."
                    )
            except Exception as e:
                # Database tables don't exist yet, that's okay during initialization
                print(f"Note: Database tables not found during app creation: {e}")

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

    from superviseme.routes.researcher import researcher as researcher_blueprint
    app.register_blueprint(researcher_blueprint)

    from superviseme.routes.profile import profile as profile_blueprint
    app.register_blueprint(profile_blueprint)

    from superviseme.routes.notifications import notifications as notifications_blueprint
    app.register_blueprint(notifications_blueprint)

    # Register error handlers
    from superviseme.routes.errors import errors as errors_blueprint
    app.register_blueprint(errors_blueprint)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        """
        Return JSON for API/fetch requests and an HTML error page for regular navigation.
        """
        wants_json = (
            request.path.startswith("/api/")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.accept_mimetypes.best == "application/json"
        )
        if wants_json:
            return jsonify({"status": "error", "message": "Invalid or missing CSRF token."}), 400
        return render_template("errors/400.html", error=error), 400

    # Set up comprehensive logging
    from superviseme.utils.logging_config import setup_logging, log_request_response
    loggers = setup_logging(app)
    log_request_response(app, loggers)

    # Initialize scheduler only when explicitly enabled, so it can run in a single worker/service.
    enable_scheduler = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
    if enable_scheduler and not app.testing:
        from superviseme.utils.task_scheduler import init_scheduler
        init_scheduler(app)
    else:
        app.logger.info(
            "Background scheduler disabled for this process",
            extra={"event_type": "scheduler_disabled", "enable_scheduler": enable_scheduler},
        )

    # Register template filters
    @app.template_filter('format_todo_links')
    def format_todo_links_filter(text, user_type='supervisor'):
        from superviseme.utils.todo_parser import format_text_with_todo_links
        base_url = f"/{user_type}/" if user_type else "/"
        return format_text_with_todo_links(text, base_url)
    
    def _sanitize_html(html):
        import bleach
        # Allow standard markdown tags plus those used in todo references
        allowed_tags = [
            'a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol',
            'strong', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'pre', 'br',
            'hr', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'div', 'span'
        ]

        allowed_attrs = {
            '*': ['class'],
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title'],
        }
        return bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs, strip=True)

    @app.template_filter('markdown')
    def markdown_filter(text):
        """Convert markdown text to HTML"""
        if not text:
            return ""
        import markdown
        html = markdown.markdown(text, extensions=['nl2br', 'fenced_code'])
        return _sanitize_html(html)
    
    @app.template_filter('markdown_with_todos')
    def markdown_with_todos_filter(text, user_type='supervisor'):
        """Convert markdown text to HTML and process todo links"""
        if not text:
            return ""
        import markdown

        # First convert markdown to HTML
        html = markdown.markdown(text, extensions=['nl2br', 'fenced_code'])

        # Sanitize HTML
        clean_html = _sanitize_html(html)

        # Then process todo links
        from superviseme.utils.todo_parser import format_text_with_todo_links
        base_url = f"/{user_type}/" if user_type else "/"
        return format_text_with_todo_links(clean_html, base_url)

    # db.create_all() for PostgreSQL is no longer needed: _run_db_upgrade()
    # above already applied all migrations (including initial table creation)
    # when the database was first created.

    # Register template globals
    @app.template_global()
    def moment():
        """Return a datetime object for the current moment"""
        from datetime import datetime
        class MomentWrapper:
            def __init__(self, dt):
                self.dt = dt
            
            def format(self, format_string):
                """Format datetime using strftime-like format but with moment.js style"""
                # Convert moment.js format to Python strftime format
                format_mapping = {
                    'YYYY': '%Y',
                    'MM': '%m', 
                    'DD': '%d',
                    'HH': '%H',
                    'mm': '%M',
                    'ss': '%S'
                }
                python_format = format_string
                for moment_fmt, python_fmt in format_mapping.items():
                    python_format = python_format.replace(moment_fmt, python_fmt)
                return self.dt.strftime(python_format)
        
        return MomentWrapper(datetime.now())

    return app
