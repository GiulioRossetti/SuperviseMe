import os
import sys
import pytest
import tempfile
import shutil
from werkzeug.security import generate_password_hash
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from superviseme import create_app, db
from superviseme.models import User_mgmt

@pytest.fixture
def app():
    # Create a temporary file to isolate the database for each test
    db_fd, db_path = tempfile.mkstemp()

    # Configure the app for testing
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    os.environ['WTF_CSRF_ENABLED'] = 'False'  # Disable CSRF for easier testing

    app = create_app(db_type="sqlite", skip_user_init=True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def admin_user(app):
    user = User_mgmt(
        username="admin_test",
        name="Admin",
        surname="Test",
        email="admin@test.com",
        password=generate_password_hash("password"),
        user_type="admin",
        joined_on=int(time.time())
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def supervisor_user(app):
    user = User_mgmt(
        username="supervisor_test",
        name="Supervisor",
        surname="Test",
        email="supervisor@test.com",
        password=generate_password_hash("password"),
        user_type="supervisor",
        joined_on=int(time.time())
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def researcher_user(app):
    user = User_mgmt(
        username="researcher_test",
        name="Researcher",
        surname="Test",
        email="researcher@test.com",
        password=generate_password_hash("password"),
        user_type="researcher",
        joined_on=int(time.time())
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def student_user(app):
    user = User_mgmt(
        username="student_test",
        name="Student",
        surname="Test",
        email="student@test.com",
        password=generate_password_hash("password"),
        user_type="student",
        joined_on=int(time.time())
    )
    db.session.add(user)
    db.session.commit()
    return user
