#!/usr/bin/env python3
"""
Database seeding script for SuperviseMe application.
Creates sample data for testing: admin, supervisors, students, and theses.
"""
import os
import sys

# Add parent directory to path to import superviseme
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load .env before any os.getenv() calls so that passwords and connection
# settings defined in .env are honoured even when they are not already
# present in the shell environment.
from dotenv import load_dotenv
load_dotenv()

from superviseme import create_app, db
from superviseme.models import User_mgmt, Thesis, Thesis_Status, Thesis_Supervisor, Thesis_Tag
from werkzeug.security import generate_password_hash
import time


def resolve_seed_password(env_var):
    password = os.getenv(env_var, "")
    if password:
        return password

    shared_password = os.getenv("SEED_DEFAULT_PASSWORD", "")
    if shared_password:
        print(f"INFO: {env_var} not set. Using SEED_DEFAULT_PASSWORD.")
        return shared_password

    print(f"WARNING: {env_var} and SEED_DEFAULT_PASSWORD not set. Falling back to 'test'.")
    return "test"


def seed_database():
    """Populate database with sample data."""
    # Use postgresql for Docker environment, sqlite for local development
    db_type = "postgresql" if os.getenv("PG_HOST") else "sqlite"
    app = create_app(db_type=db_type)
    
    with app.app_context():
        print("Starting database seeding...")
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        print("Clearing existing data...")
        from superviseme.models import (
            Notification, OrcidActivity, ResearchProject, ResearchProject_Collaborator, ResearchProject_Dataset,
            ResearchProject_Milestone, ResearchProject_Publication, ResearchProject_Resource, ResearchProject_Review,
            ResearchProject_Software, ResearchProject_Thesis, Supervisor_Role,
        )
        for model in (ResearchProject_Review, ResearchProject_Resource, ResearchProject_Thesis, ResearchProject_Dataset,
                      ResearchProject_Software, ResearchProject_Milestone, ResearchProject_Publication, ResearchProject_Collaborator,
                      Supervisor_Role, Notification, OrcidActivity):
            model.query.delete()
        ResearchProject.query.update({"parent_id": None})
        ResearchProject.query.delete()
        Thesis_Tag.query.delete()
        Thesis_Supervisor.query.delete()
        Thesis_Status.query.delete()
        Thesis.query.delete()
        User_mgmt.query.delete()
        db.session.commit()

        # Create admin user
        print("Creating admin user...")
        admin_password = resolve_seed_password("ADMIN_BOOTSTRAP_PASSWORD")
        admin_user = User_mgmt(
            username='admin',
            name='Dr.',
            surname='God',
            email='admin@supervise.me',
            password=generate_password_hash(admin_password, method='pbkdf2:sha256'),
            user_type='admin',
            joined_on=int(time.time()),
            is_enabled=True
        )
        db.session.add(admin_user)
        db.session.commit()

        # Create sample supervisors
        print("Creating supervisors...")
        supervisor_password = resolve_seed_password("SEED_SUPERVISOR_PASSWORD")
        supervisors_data = [
            {
                'username': 'prof_smith', 
                'name': 'John', 
                'surname': 'Smith',
                'email': 'j.smith@university.edu',
                'cdl': 'Computer Science',
                'gender': 'Male',
                'nationality': 'American'
            },
            {
                'username': 'prof_johnson',
                'name': 'Emily', 
                'surname': 'Johnson',
                'email': 'e.johnson@university.edu', 
                'cdl': 'Data Science',
                'gender': 'Female',
                'nationality': 'British'
            },
            {
                'username': 'prof_garcia',
                'name': 'Maria',
                'surname': 'Garcia',
                'email': 'm.garcia@university.edu',
                'cdl': 'Artificial Intelligence', 
                'gender': 'Female',
                'nationality': 'Spanish'
            }
        ]
        
        supervisors = []
        for sup_data in supervisors_data:
            supervisor = User_mgmt(
                username=sup_data['username'],
                name=sup_data['name'],
                surname=sup_data['surname'],
                email=sup_data['email'],
                password=generate_password_hash(supervisor_password, method='pbkdf2:sha256'),
                user_type='supervisor',
                cdl=sup_data['cdl'],
                gender=sup_data['gender'],
                nationality=sup_data['nationality'],
                joined_on=int(time.time()),
                is_enabled=True
            )
            supervisors.append(supervisor)
            db.session.add(supervisor)
        
        # Create sample students
        print("Creating students...")
        student_password = resolve_seed_password("SEED_STUDENT_PASSWORD")
        students_data = [
            {
                'username': 'alice_doe',
                'name': 'Alice',
                'surname': 'Doe', 
                'email': 'alice.doe@student.university.edu',
                'cdl': 'Computer Science',
                'gender': 'Female',
                'nationality': 'Canadian'
            },
            {
                'username': 'bob_wilson',
                'name': 'Bob',
                'surname': 'Wilson',
                'email': 'bob.wilson@student.university.edu',
                'cdl': 'Data Science', 
                'gender': 'Male',
                'nationality': 'Australian'
            },
            {
                'username': 'carol_brown',
                'name': 'Carol',
                'surname': 'Brown',
                'email': 'carol.brown@student.university.edu',
                'cdl': 'Computer Science',
                'gender': 'Female', 
                'nationality': 'German'
            },
            {
                'username': 'david_miller',
                'name': 'David',
                'surname': 'Miller',
                'email': 'david.miller@student.university.edu',
                'cdl': 'Artificial Intelligence',
                'gender': 'Male',
                'nationality': 'French'
            },
            {
                'username': 'eva_clark',
                'name': 'Eva',
                'surname': 'Clark',
                'email': 'eva.clark@student.university.edu',
                'cdl': 'Data Science',
                'gender': 'Female',
                'nationality': 'Swedish'
            }
        ]
        
        students = []
        for std_data in students_data:
            student = User_mgmt(
                username=std_data['username'],
                name=std_data['name'],
                surname=std_data['surname'],
                email=std_data['email'],
                password=generate_password_hash(student_password, method='pbkdf2:sha256'),
                user_type='student',
                cdl=std_data['cdl'],
                gender=std_data['gender'],
                nationality=std_data['nationality'],
                joined_on=int(time.time()),
                is_enabled=True
            )
            students.append(student)
            db.session.add(student)
        
        db.session.commit()
        
        # Create sample theses
        print("Creating theses...")
        theses_data = [
            {
                'title': 'Machine Learning for Predictive Analytics in Healthcare',
                'description': 'This thesis explores the application of machine learning algorithms for predictive analytics in healthcare systems, focusing on early disease detection and treatment optimization.',
                'level': 'master',
                'author': students[0],  # Alice
                'supervisor': supervisors[0]  # Prof Smith
            },
            {
                'title': 'Deep Learning Approaches for Natural Language Processing',
                'description': 'An investigation into advanced deep learning techniques for natural language processing, with emphasis on transformer architectures and their applications in multilingual text analysis.',
                'level': 'bachelor', 
                'author': students[1],  # Bob
                'supervisor': supervisors[1]  # Prof Johnson
            },
            {
                'title': 'Blockchain Technology in Supply Chain Management',
                'description': 'This research examines the implementation of blockchain technology in supply chain management systems, analyzing security, transparency, and efficiency improvements.',
                'level': 'master',
                'author': students[2],  # Carol
                'supervisor': supervisors[2]  # Prof Garcia
            },
            {
                'title': 'Computer Vision for Autonomous Vehicle Navigation',
                'description': 'Development and evaluation of computer vision algorithms for autonomous vehicle navigation in complex urban environments, including obstacle detection and path planning.',
                'level': 'master',
                'author': students[3],  # David  
                'supervisor': supervisors[0]  # Prof Smith
            },
            {
                'title': 'Quantum Computing Applications in Cryptography',
                'description': 'An exploration of quantum computing applications in modern cryptography, analyzing both opportunities and threats to current encryption methods.',
                'level': 'bachelor',
                'author': students[4],  # Eva
                'supervisor': supervisors[1]  # Prof Johnson
            },
            {
                'title': 'IoT Security Framework for Smart Cities',
                'description': 'Design and implementation of a comprehensive security framework for Internet of Things devices in smart city infrastructures.',
                'level': 'other',
                'author': None,  # Available thesis
                'supervisor': supervisors[2]  # Prof Garcia
            },
            {
                'title': 'AI-Driven Personalized Learning Systems',
                'description': 'Development of artificial intelligence algorithms for creating personalized learning experiences in online education platforms.',
                'level': 'bachelor',
                'author': None,  # Available thesis
                'supervisor': supervisors[0]  # Prof Smith
            }
        ]
        
        theses = []
        for thesis_data in theses_data:
            thesis = Thesis(
                title=thesis_data['title'],
                description=thesis_data['description'],
                level=thesis_data['level'],
                author_id=thesis_data['author'].id if thesis_data['author'] else None,
                frozen=False,
                created_at=int(time.time())
            )
            theses.append(thesis)
            db.session.add(thesis)
        
        db.session.commit()
        
        # Create thesis-supervisor relationships
        print("Creating thesis-supervisor relationships...")
        for i, thesis in enumerate(theses):
            thesis_supervisor = Thesis_Supervisor(
                thesis_id=thesis.id,
                supervisor_id=theses_data[i]['supervisor'].id,
                assigned_at=int(time.time())
            )
            db.session.add(thesis_supervisor)
        
        # Create thesis statuses
        print("Creating thesis statuses...")
        statuses = ['thesis accepted', 'in progress', 'completed', 'under review']
        for i, thesis in enumerate(theses):
            status = statuses[i % len(statuses)]
            thesis_status = Thesis_Status(
                thesis_id=thesis.id,
                status=status,
                updated_at=int(time.time())
            )
            db.session.add(thesis_status)
        
        # Create sample tags
        print("Creating thesis tags...")
        tags_data = [
            ['machine learning', 'healthcare', 'predictive analytics'],
            ['deep learning', 'NLP', 'transformers'],
            ['blockchain', 'supply chain', 'security'],
            ['computer vision', 'autonomous vehicles', 'AI'],
            ['quantum computing', 'cryptography', 'security'],
            ['IoT', 'smart cities', 'security'],
            ['AI', 'personalized learning', 'education']
        ]
        
        for i, thesis in enumerate(theses):
            for tag_name in tags_data[i]:
                tag = Thesis_Tag(
                    thesis_id=thesis.id,
                    tag=tag_name
                )
                db.session.add(tag)
        
        db.session.commit()
        
        # Create researchers
        print("Creating researchers...")
        researcher_password = resolve_seed_password("SEED_RESEARCHER_PASSWORD")
        researchers_data = [
            {
                'username': 'dr_alice',
                'name': 'Alice',
                'surname': 'Johnson',
                'email': 'alice.johnson@university.edu',
                'cdl': 'Computer Science',
                'gender': 'Female',
                'nationality': 'Canadian'
            },
            {
                'username': 'dr_bob',
                'name': 'Bob',
                'surname': 'Williams', 
                'email': 'bob.williams@university.edu',
                'cdl': 'Data Science',
                'gender': 'Male',
                'nationality': 'American'
            },
            {
                'username': 'dr_maria',
                'name': 'Maria',
                'surname': 'Rodriguez',
                'email': 'maria.rodriguez@university.edu',
                'cdl': 'Artificial Intelligence',
                'gender': 'Female',
                'nationality': 'Spanish'
            }
        ]
        
        researchers = []
        for researcher_data in researchers_data:
            researcher = User_mgmt(
                username=researcher_data['username'],
                name=researcher_data['name'],
                surname=researcher_data['surname'],
                email=researcher_data['email'],
                password=generate_password_hash(researcher_password, method='pbkdf2:sha256'),
                user_type='researcher',
                cdl=researcher_data['cdl'],
                gender=researcher_data['gender'],
                nationality=researcher_data['nationality'],
                joined_on=int(time.time()),
                is_enabled=True
            )
            researchers.append(researcher)
            db.session.add(researcher)
        
        db.session.commit()
        
        # Create research projects
        print("Creating research projects...")
        from superviseme.models import ResearchProject, ResearchProject_Collaborator, Supervisor_Role
        
        projects_data = [
            {
                'title': 'Machine Learning for Climate Prediction',
                'description': 'A comprehensive study on using advanced ML algorithms to improve climate change prediction models, focusing on temperature and precipitation forecasting.',
                'researcher': researchers[0],  # Dr. Alice
                'level': 'research'
            },
            {
                'title': 'Social Network Analysis in Online Communities',
                'description': 'Investigating patterns of interaction and influence in online social networks, analyzing user behavior and community formation.',
                'researcher': researchers[1],  # Dr. Bob
                'level': 'full-scale'
            },
            {
                'title': 'Ethics in Artificial Intelligence Systems',
                'description': 'Examining ethical considerations in AI development, including bias detection, fairness algorithms, and responsible AI deployment.',
                'researcher': researchers[2],  # Dr. Maria
                'level': 'longitudinal'
            },
            {
                'title': 'Quantum Computing Applications in Healthcare',
                'description': 'Exploring the potential of quantum computing in medical research, drug discovery, and personalized medicine applications.',
                'researcher': researchers[0],  # Dr. Alice (second project)
                'level': 'pilot'
            }
        ]
        
        projects = []
        for project_data in projects_data:
            project = ResearchProject(
                title=project_data['title'],
                description=project_data['description'],
                researcher_id=project_data['researcher'].id,
                level=project_data['level'],
                frozen=False,
                created_at=int(time.time())
            )
            projects.append(project)
            db.session.add(project)
        
        db.session.commit()
        
        # Create collaborations
        print("Creating research collaborations...")
        collaborations = [
            # Dr. Bob collaborates on Dr. Alice's ML project
            {
                'project': projects[0],  # ML for Climate Prediction
                'collaborator': researchers[1],  # Dr. Bob
                'role': 'co-investigator'
            },
            # Dr. Maria collaborates on Dr. Bob's social network project
            {
                'project': projects[1],  # Social Network Analysis
                'collaborator': researchers[2],  # Dr. Maria
                'role': 'collaborator'
            },
            # Dr. Alice collaborates on Dr. Maria's ethics project
            {
                'project': projects[2],  # Ethics in AI
                'collaborator': researchers[0],  # Dr. Alice
                'role': 'advisor'
            }
        ]
        
        for collab_data in collaborations:
            collaboration = ResearchProject_Collaborator(
                project_id=collab_data['project'].id,
                collaborator_id=collab_data['collaborator'].id,
                role=collab_data['role'],
                added_at=int(time.time())
            )
            db.session.add(collaboration)
        
        db.session.commit()
        
        # Grant supervisor roles
        print("Granting supervisor roles...")
        # Make Dr. Alice and Dr. Maria supervisors (Dr. Bob remains researcher-only)
        supervisor_grants = [
            {'researcher': researchers[0], 'granted_by_id': admin_user.id},  # Dr. Alice
            {'researcher': researchers[2], 'granted_by_id': admin_user.id}   # Dr. Maria
        ]
        
        for grant in supervisor_grants:
            supervisor_role = Supervisor_Role(
                researcher_id=grant['researcher'].id,
                granted_by=grant['granted_by_id'],
                granted_at=int(time.time()),
                active=True,
                created_at=int(time.time()),
                updated_at=int(time.time())
            )
            db.session.add(supervisor_role)
        
        db.session.commit()
        
        # Research output: metadata, sub-project, invitations, publications, funding, milestones, datasets,
        # linked theses, internal reviews, ORCID record and a public project page
        print("Creating research output demo data...")
        import json
        from superviseme.models import (
            Notification, OrcidActivity, ResearchProject_Dataset, ResearchProject_Milestone, ResearchProject_Publication,
            ResearchProject_Resource, ResearchProject_Review, ResearchProject_Software, ResearchProject_Thesis,
        )
        now = int(time.time())
        day = 86400
        alice, bob, maria = researchers[0], researchers[1], researchers[2]
        climate, social, ethics, quantum = projects

        # Metadata shown on project cards / portfolio (levels: see utils/projects.py)
        climate.level, climate.area, climate.tags = "programme", "Climate science", "machine learning,climate,forecasting"
        social.level, social.area, social.tags = "full-scale", "Computational social science", "networks,communities"
        ethics.level, ethics.area, ethics.tags = "longitudinal", "AI ethics", "fairness,bias"
        quantum.level, quantum.area, quantum.tags = "pilot", "Quantum computing", "quantum,healthcare"
        climate.created_at, social.created_at, ethics.created_at, quantum.created_at = (
            now - 700 * day, now - 400 * day, now - 120 * day, now - 30 * day)

        # A paper under the climate programme (sub-project)
        paper = ResearchProject(
            title="Precipitation nowcasting with graph networks", description="Paper within the climate programme: short-term rainfall forecasting.",
            researcher_id=alice.id, level="paper", area="Climate science", tags="machine learning,nowcasting",
            parent_id=climate.id, frozen=False, created_at=now - 90 * day)
        db.session.add(paper)
        db.session.flush()

        # Funding
        climate.funder, climate.grant_id, climate.start_date, climate.end_date = "European Research Council", "ERC-2024-STG-101", "2024-01-01", "2027-12-31"
        social.funder, social.grant_id, social.start_date, social.end_date = "PRIN (MUR)", "2022ABCDE", "2023-06-01", "2026-05-31"

        # Collaboration states: accepted roles, a pending invitation (Maria -> climate) and a read-only viewer (Bob -> ethics)
        db.session.add(ResearchProject_Collaborator(project_id=climate.id, collaborator_id=maria.id, role="collaborator",
                                                    status="pending", added_at=now - 2 * day))
        db.session.add(Notification(recipient_id=maria.id, actor_id=alice.id, notification_type="project_invitation",
                                    title=f"Invitation to project: {climate.title}",
                                    message=f"{alice.name} {alice.surname} invited you to collaborate on \"{climate.title}\" as collaborator. Accept or decline from your dashboard.",
                                    action_url="/researcher/dashboard", created_at=now - 2 * day))
        db.session.add(ResearchProject_Collaborator(project_id=ethics.id, collaborator_id=bob.id, role="viewer",
                                                    status="accepted", added_at=now - 20 * day))

        # Publications (BibTeX export, portfolio chart, public page)
        pubs = [
            (climate, "Deep learning for monthly temperature anomaly forecasting", "Alice Johnson, Bob Williams", 2025, "Journal of Climate Informatics", "10.1000/jci.2025.001", "article"),
            (climate, "A benchmark for sub-seasonal precipitation prediction", "Alice Johnson", 2024, "Proc. NeurIPS Climate Workshop", "10.1000/nips.2024.017", "conference"),
            (social, "Community formation in online forums", "Bob Williams, Maria Rodriguez", 2024, "Social Networks", "10.1000/sn.2024.042", "article"),
            (social, "Influence and homophily: a longitudinal study", "Bob Williams", 2023, "Network Science", "10.1000/ns.2023.009", "article"),
            (ethics, "Auditing fairness in hiring algorithms", "Maria Rodriguez", 2025, "AI & Society", None, "preprint"),
        ]
        for proj, title, authors, year, venue, doi, kind in pubs:
            db.session.add(ResearchProject_Publication(
                project_id=proj.id, title=title, authors=authors, year=year, venue=venue, doi=doi, pub_type=kind,
                url=f"https://doi.org/{doi}" if doi else None, added_by=proj.researcher_id, created_at=now - day))

        # Milestones: one overdue, some upcoming (agenda and .ics feed), one done
        for proj, title, offset, status in [
            (climate, "D1.1 Data collection report", -10, "pending"), (climate, "D2.1 Model prototype", 25, "pending"),
            (climate, "Mid-term review", 120, "pending"), (climate, "D1.0 Kick-off meeting", -300, "done"),
            (social, "Final report to the funder", 60, "pending"), (ethics, "Workshop submission", 14, "pending"),
        ]:
            db.session.add(ResearchProject_Milestone(project_id=proj.id, title=title, due_date=now + offset * day + 12 * 3600,
                                                     status=status, created_at=now - 30 * day))

        # Datasets with FAIR checklist
        db.session.add(ResearchProject_Dataset(project_id=climate.id, title="European monthly temperature grid (2000-2024)",
                                               doi="10.5281/zenodo.1234567", url="https://zenodo.org/record/1234567", license="CC-BY-4.0",
                                               fair="findable,accessible,interoperable,reusable", created_at=now - 40 * day))
        db.session.add(ResearchProject_Dataset(project_id=social.id, title="Anonymised forum interaction graph",
                                               url="https://github.com/example/forum-graph", license="ODbL",
                                               fair="findable,accessible", created_at=now - 60 * day))

        # Software produced by the projects
        db.session.add(ResearchProject_Software(project_id=climate.id, title="climate-grid-tools", version="1.2.0", language="Python",
                                                license="MIT", repo_url="https://github.com/example/climate-grid-tools", doi="10.5281/zenodo.7654321",
                                                description="Utilities to download, regrid and validate gridded climate data.", created_at=now - 30 * day))
        db.session.add(ResearchProject_Software(project_id=social.id, title="forum-graph-builder", version="0.4", language="Python", license="Apache-2.0",
                                                repo_url="https://github.com/example/forum-graph-builder", created_at=now - 50 * day))

        db.session.add(ResearchProject_Software(project_id=ethics.id, title="fairness-audit-kit", version="2.1.0", language="R", license="GPL-3.0",
                                                repo_url="https://gitlab.com/example/fairness-audit-kit", doi="10.5281/zenodo.8123456",
                                                description="Checklist and scripts to audit classifiers for group fairness.", created_at=now - 20 * day))
        db.session.add(ResearchProject_Software(project_id=quantum.id, title="qsim-notebooks", version="0.1", language="Jupyter Notebook",
                                                license="BSD-3-Clause", repo_url="https://github.com/example/qsim-notebooks", created_at=now - 10 * day))
        db.session.add(ResearchProject_Dataset(project_id=ethics.id, title="Survey on perceived algorithmic fairness (N=1,200)",
                                               doi="10.5281/zenodo.8000001", license="CC0-1.0", fair="findable,interoperable,reusable",
                                               created_at=now - 25 * day))

        # Theses done within projects (supervised by Alice / Maria, or published by them)
        for proj, thesis_obj in [(climate, theses[0]), (social, theses[1]), (ethics, theses[2])]:
            db.session.add(ResearchProject_Thesis(project_id=proj.id, thesis_id=thesis_obj.id, created_at=now - 10 * day))

        # Resources and internal review requests (Alice <-> Bob on the climate programme)
        draft = ResearchProject_Resource(project_id=climate.id, resource_type="link", resource_url="https://example.org/drafts/climate-paper-v2.pdf",
                                         description="Paper draft v2", created_at=now - 6 * day)
        proto = ResearchProject_Resource(project_id=climate.id, resource_type="link", resource_url="https://example.org/drafts/protocol.pdf",
                                         description="Data protocol", created_at=now - 12 * day)
        db.session.add_all([draft, proto])
        db.session.flush()
        db.session.add(ResearchProject_Review(project_id=climate.id, resource_id=draft.id, requested_by=alice.id, reviewer_id=bob.id,
                                              note="Could you check sections 3 and 4 before submission?", status="pending",
                                              created_at=now - 3 * day, updated_at=now - 3 * day))
        db.session.add(ResearchProject_Review(project_id=climate.id, resource_id=proto.id, requested_by=alice.id, reviewer_id=bob.id,
                                              note="Protocol review", status="approved", comment="Looks good, minor typos fixed.",
                                              created_at=now - 10 * day, updated_at=now - 8 * day))
        db.session.add(Notification(recipient_id=bob.id, actor_id=alice.id, notification_type="project_review_request",
                                    title=f"Review requested: {climate.title}",
                                    message=f"{alice.name} {alice.surname} asked you to review a resource of \"{climate.title}\".",
                                    action_url=f"/researcher/project/{climate.id}/output#reviews", created_at=now - 3 * day))

        # Public page: climate (description, funding, publications, datasets, team), social (description, publications)
        climate.is_public, climate.public_fields = True, "description,funding,publications,datasets,collaborators"
        social.is_public, social.public_fields = True, "description,publications"

        # ORCID record of Dr. Alice (what "Import from your ORCID record" offers) and affiliations shown in the Team card
        alice.orcid_id = "0000-0002-1825-0097"
        bob.orcid_id = "0000-0001-5109-3700"
        def activity(user, title, kind, org=None, year=None, ext=None):
            db.session.add(OrcidActivity(user_id=user.id, title=title, type=kind, organization=org, publication_date=year,
                                         external_ids=json.dumps(ext or []), created_at=now, updated_at=now))
        activity(alice, "Probabilistic downscaling of climate model output", "journal-article", year="2022",
                 ext=[{"type": "doi", "value": "10.1000/pdcm.2022.5", "url": None}])
        activity(alice, "Learning-based bias correction for precipitation", "conference-paper", year="2023",
                 ext=[{"type": "doi", "value": "10.1000/lbbc.2023.8", "url": None}])
        activity(alice, "Deep learning for monthly temperature anomaly forecasting", "journal-article", year="2025",
                 ext=[{"type": "doi", "value": "10.1000/jci.2025.001", "url": None}])  # already in the project: not offered
        activity(alice, "ERC Starting Grant - Climate learning", "funding", org="European Research Council", year="2024",
                 ext=[{"type": "grant_number", "value": "ERC-2024-STG-101", "url": None}])
        activity(alice, "Associate Researcher", "employment", org="Institute of Information Science and Technologies, CNR", year="2021")
        activity(alice, "PhD in Computer Science", "education", org="University of Pisa", year="2016")
        activity(bob, "Researcher", "employment", org="University of Pisa", year="2020")
        db.session.commit()

        print("Database seeding completed successfully!")
        print(f"Created:")
        print(f"  - 1 admin user (username: admin, password from ADMIN_BOOTSTRAP_PASSWORD)")
        print(f"  - {len(supervisors)} supervisors (password from SEED_SUPERVISOR_PASSWORD/SEED_DEFAULT_PASSWORD)")
        print(f"  - {len(students)} students (password from SEED_STUDENT_PASSWORD/SEED_DEFAULT_PASSWORD)")
        print(f"  - {len(researchers)} researchers (password from SEED_RESEARCHER_PASSWORD/SEED_DEFAULT_PASSWORD)")
        print(f"  - {len(theses)} theses (5 assigned, 2 available)")
        print(f"  - {len(projects)} research projects")
        print(f"  - {len(collaborations)} research collaborations")
        print(f"  - 2 supervisor role grants (Dr. Alice & Dr. Maria)")
        print(f"  - Thesis statuses and tags")
        print(f"  - Research output demo: sub-project, funding, 5 publications, milestones (1 overdue), 3 datasets, 4 software packages,")
        print(f"    thesis links, 2 review requests, a pending invitation (Dr. Maria), a viewer (Dr. Bob),")
        print(f"    ORCID record for Dr. Alice (imports + affiliations) and 2 public project pages")

if __name__ == '__main__':
    seed_database()
