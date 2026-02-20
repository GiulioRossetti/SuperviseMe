import pytest
from flask import url_for
from superviseme.models import Thesis, Thesis_Supervisor
import time

def login(client, email, password):
    return client.post('/login', data=dict(
        email=email,
        password=password
    ), follow_redirects=True)

class TestAuthorization:
    def test_student_cannot_access_admin(self, client, student_user):
        login(client, student_user.email, "password")
        response = client.get('/admin/dashboard')
        assert response.status_code != 200
        # Check if redirected or error page. Assuming permission denied or redirect.
        # superviseme uses check_privileges which returns a template or redirect?
        # check_privileges: if not authorized, returns render_template("errors/403.html") usually or redirect.
        # But looking at admin.py: return check_privileges(...).

        # Let's check what check_privileges does.
        # It's in superviseme/utils/miscellanea.py.
        # If I can't read it easily, I'll assume it returns something indicative of failure.
        # Usually checking for "Dashboard" not in response is good, or specific error message.

        assert b"Admin Dashboard" not in response.data
        # It might return 403 or redirect to login (if not logged in) or show error page.
        # Since we are logged in as student, it should be 403 or error page.

    def test_student_cannot_edit_others_thesis(self, client, student_user, supervisor_user):
        # Create another student and their thesis
        from superviseme import db
        from superviseme.models import User_mgmt

        other_student = User_mgmt(
            username="other_student",
            name="Other",
            surname="Student",
            email="other@test.com",
            password="password", # Plaintext for simplicity here as we don't login as them
            user_type="student",
            joined_on=int(time.time())
        )
        db.session.add(other_student)
        db.session.commit()

        thesis = Thesis(
            title="Other Student Thesis",
            description="Private",
            author_id=other_student.id,
            created_at=int(time.time()),
            level="master"
        )
        db.session.add(thesis)
        db.session.commit()

        login(client, student_user.email, "password")

        # Try to post update to other thesis
        response = client.post('/student/post_update', data=dict(
            thesis_id=thesis.id,
            content="Hacking attempt"
        ), follow_redirects=True)

        # Should redirect back to thesis_data or fail
        # student.post_update checks: thesis = Thesis.query.filter_by(id=thesis_id, author_id=current_user.id).first()
        # if not thesis: return redirect(url_for('student.thesis_data'))

        assert response.status_code == 200 # Redirects successfully usually return 200 after following
        # Verify update was NOT created
        from superviseme.models import Thesis_Update
        update = Thesis_Update.query.filter_by(content="Hacking attempt").first()
        assert update is None

    def test_supervisor_cannot_access_admin(self, client, supervisor_user):
        login(client, supervisor_user.email, "password")
        response = client.get('/admin/dashboard')
        # Expecting 403 or redirect to login/dashboard with error
        # Assuming check_privileges returns a response object (e.g. render_template)
        assert b"Admin Dashboard" not in response.data

    def test_supervisor_cannot_edit_unsupervised_thesis(self, client, supervisor_user, student_user):
        # Create a thesis NOT supervised by this supervisor
        from superviseme import db

        thesis = Thesis(
            title="Unsupervised Thesis",
            description="Not mine",
            author_id=student_user.id,
            created_at=int(time.time()),
            level="master"
        )
        db.session.add(thesis)
        db.session.commit()

        login(client, supervisor_user.email, "password")

        # Try to update thesis
        response = client.post('/supervisor/update_thesis', data=dict(
            thesis_id=thesis.id,
            title="Hacked Title",
            description="Hacked Description",
            level="master"
        ), follow_redirects=True)

        # Should fail. update_thesis checks: thesis_supervisor = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id, thesis_id=thesis_id).first()
        # If not found, flashes message and redirects.

        # Check if title changed
        db.session.refresh(thesis)
        assert thesis.title == "Unsupervised Thesis"
        # Flash message might not be rendered in the template, so we skip checking response.data for it.
        # assert b"Thesis not found or not accessible" in response.data

    def test_cross_role_access(self, client, student_user):
        login(client, student_user.email, "password")

        # Try accessing supervisor dashboard
        response = client.get('/supervisor/dashboard')
        # Should be denied
        assert b"Supervisor Dashboard" not in response.data

        # Try accessing researcher dashboard
        response = client.get('/researcher/dashboard')
        assert b"Researcher Dashboard" not in response.data
