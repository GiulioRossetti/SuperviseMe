import pytest
import time
from flask import url_for
from superviseme.models import User_mgmt, Thesis, Todo, ResearchProject, Thesis_Update, Resource, Thesis_Objective, Thesis_Hypothesis, MeetingNote

def login(client, email, password):
    return client.post('/login', data=dict(
        email=email,
        password=password
    ), follow_redirects=True)

def logout(client):
    return client.get('/logout', follow_redirects=True)

class TestAdminWorkflow:
    def test_admin_full_workflow(self, client, admin_user, student_user):
        # Login
        login(client, admin_user.email, "password")

        # 1. Dashboard Access
        response = client.get('/admin/dashboard')
        assert response.status_code == 200
        assert b"Dashboard" in response.data

        # 2. User CRUD
        # Create Supervisor
        response = client.post('/admin/create_user', data=dict(
            username="new_supervisor",
            name="New",
            surname="Supervisor",
            email="new_supervisor@test.com",
            password="password123",
            password2="password123",
            role="supervisor",
            gender="M",
            nationality="IT"
        ), follow_redirects=True)
        assert response.status_code == 200
        supervisor = User_mgmt.query.filter_by(username="new_supervisor").first()
        assert supervisor is not None
        assert supervisor.user_type == "supervisor"

        # 3. Thesis CRUD
        # Create Thesis
        response = client.post('/admin/create_thesis', data=dict(
            title="Admin Created Thesis",
            description="Created by Admin",
            student_id=student_user.id,
            supervisor_id=supervisor.id,
            level="master"
        ), follow_redirects=True)
        assert response.status_code == 200
        thesis = Thesis.query.filter_by(title="Admin Created Thesis").first()
        assert thesis is not None
        assert thesis.author_id == student_user.id

        # Update Thesis
        response = client.post('/admin/update_thesis', data=dict(
            thesis_id=thesis.id,
            title="Updated Admin Thesis",
            description="Updated Description",
            level="bachelor"
        ), follow_redirects=True)
        assert response.status_code == 200
        db_thesis = Thesis.query.get(thesis.id)
        assert db_thesis.title == "Updated Admin Thesis"

        # Delete Thesis
        # Create a dummy thesis to delete so we don't break other tests using 'thesis' if any
        response = client.post('/admin/create_thesis', data=dict(
            title="To Delete",
            description="Delete me",
            student_id="",
            supervisor_id="",
            level="master"
        ), follow_redirects=True)
        to_delete = Thesis.query.filter_by(title="To Delete").first()

        response = client.delete(f'/admin/delete_thesis/{to_delete.id}')
        assert response.status_code == 200
        assert Thesis.query.get(to_delete.id) is None


class TestSupervisorWorkflow:
    def test_supervisor_full_workflow(self, client, supervisor_user, student_user):
        # Setup: Create a thesis assigned to this supervisor
        from superviseme import db
        with client.application.app_context():
            thesis = Thesis(
                title="Supervisor Workflow Thesis",
                description="Test Description",
                author_id=student_user.id,
                created_at=int(time.time()),
                level="master"
            )
            db.session.add(thesis)
            db.session.commit()

            from superviseme.models import Thesis_Supervisor
            ts = Thesis_Supervisor(
                thesis_id=thesis.id,
                supervisor_id=supervisor_user.id,
                assigned_at=int(time.time())
            )
            db.session.add(ts)
            db.session.commit()
            thesis_id = thesis.id

        # Login
        login(client, supervisor_user.email, "password")

        # 1. Dashboard
        response = client.get('/supervisor/dashboard')
        assert response.status_code == 200
        assert b"Supervisor Workflow Thesis" in response.data

        # 2. Thesis Details
        response = client.get(f'/supervisor/thesis/{thesis_id}')
        assert response.status_code == 200

        # 3. Post Update
        response = client.post('/supervisor/post_update', data=dict(
            thesis_id=thesis_id,
            content="Supervisor update content"
        ), follow_redirects=True)
        assert response.status_code == 200
        assert b"Supervisor update content" in response.data

        # 4. Add Todo
        response = client.post('/supervisor/add_todo', data=dict(
            thesis_id=thesis_id,
            title="Supervisor Task",
            description="Do this",
            priority="high",
            assigned_to_id=student_user.id
        ), follow_redirects=True)
        assert response.status_code == 200
        todo = Todo.query.filter_by(title="Supervisor Task").first()
        assert todo is not None
        assert todo.thesis_id == thesis_id

        # 5. Toggle Todo
        response = client.post(f'/supervisor/toggle_todo/{todo.id}', follow_redirects=True)
        assert response.status_code == 200
        todo = Todo.query.get(todo.id)
        assert todo.status == "completed"

        # 6. Add Meeting Note
        response = client.post('/supervisor/add_meeting_note', data=dict(
            thesis_id=thesis_id,
            title="Meeting 1",
            content="Notes from meeting"
        ), follow_redirects=True)
        assert response.status_code == 200
        note = MeetingNote.query.filter_by(title="Meeting 1").first()
        assert note is not None


class TestStudentWorkflow:
    def test_student_full_workflow(self, client, student_user, supervisor_user):
        # Setup: Ensure student has a thesis
        from superviseme import db
        with client.application.app_context():
            # Check if student already has a thesis (from previous tests)
            existing_thesis = Thesis.query.filter_by(author_id=student_user.id).first()
            if not existing_thesis:
                thesis = Thesis(
                    title="Student Thesis",
                    description="My Thesis",
                    author_id=student_user.id,
                    created_at=int(time.time()),
                    level="master"
                )
                db.session.add(thesis)
                db.session.commit()
                thesis_id = thesis.id
            else:
                thesis_id = existing_thesis.id

        # Login
        login(client, student_user.email, "password")

        # 1. Dashboard
        response = client.get('/student/dashboard')
        assert response.status_code == 200

        # 2. Thesis Page
        response = client.get('/student/thesis')
        assert response.status_code == 200

        # 3. Post Update
        response = client.post('/student/post_update', data=dict(
            thesis_id=thesis_id,
            content="Student progress report"
        ), follow_redirects=True)
        assert response.status_code == 200
        # Verify update exists
        update = Thesis_Update.query.filter_by(content="Student progress report").first()
        assert update is not None

        # 4. Add Resource
        response = client.post('/student/add_resource', data=dict(
            thesis_id=thesis_id,
            resource_type="link",
            resource_link="http://example.com",
            description="Useful link"
        ), follow_redirects=True)
        assert response.status_code == 200
        resource = Resource.query.filter_by(resource_url="http://example.com").first()
        assert resource is not None

        # 5. Add Objective
        response = client.post('/student/add_objective', data=dict(
            thesis_id=thesis_id,
            title="Objective 1",
            description="First objective"
        ), follow_redirects=True)
        assert response.status_code == 200
        obj = Thesis_Objective.query.filter_by(title="Objective 1").first()
        assert obj is not None


class TestResearcherWorkflow:
    def test_researcher_full_workflow(self, client, researcher_user):
        login(client, researcher_user.email, "password")

        # 1. Create Project
        response = client.post('/researcher/create_project', data=dict(
            title="New Research Project",
            description="Exciting research",
            level="research"
        ), follow_redirects=True)
        assert response.status_code == 200
        project = ResearchProject.query.filter_by(title="New Research Project").first()
        assert project is not None
        assert project.researcher_id == researcher_user.id

        # 2. Project Detail
        response = client.get(f'/researcher/project/{project.id}')
        assert response.status_code == 200

        # 3. Add Project Update
        response = client.post(f'/researcher/project/{project.id}/add_update', data=dict(
            content="Project started",
            update_type="progress"
        ), follow_redirects=True)
        assert response.status_code == 200

        # 4. Add Project Todo
        response = client.post(f'/researcher/project/{project.id}/add_todo', data=dict(
            title="Research Task",
            description="Do research",
            priority="high",
            assigned_to_id=researcher_user.id
        ), follow_redirects=True)
        assert response.status_code == 200

    def test_researcher_dual_role(self, client, researcher_user, admin_user):
        # Grant supervisor role to researcher
        login(client, admin_user.email, "password")
        client.post('/admin/grant_supervisor_role', data=dict(
            researcher_id=researcher_user.id
        ), follow_redirects=True)
        logout(client)

        # Login as researcher
        login(client, researcher_user.email, "password")

        # Check access to supervisor dashboard
        response = client.get('/researcher/supervisor/dashboard')
        assert response.status_code == 200
