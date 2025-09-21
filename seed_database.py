#!/usr/bin/env python3
"""
Database seeding script for SuperviseMe application.
Creates sample data for testing: admin, supervisors, students, and theses.
"""
import os
from superviseme import create_app, db
from superviseme.models import User_mgmt, Thesis, Thesis_Status, Thesis_Supervisor, Thesis_Tag
from werkzeug.security import generate_password_hash
import time

def seed_database():
    """Populate database with sample data."""
    # Use postgresql for Docker environment, sqlite for local development
    db_type = "postgresql" if os.getenv("PG_HOST") else "sqlite"
    app = create_app(db_type=db_type)
    
    with app.app_context():
        print("Starting database seeding...")
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        print("Clearing existing data...")
        Thesis_Tag.query.delete()
        Thesis_Supervisor.query.delete()
        Thesis_Status.query.delete()
        Thesis.query.delete()
        # Keep admin user but remove others for fresh start
        User_mgmt.query.filter(User_mgmt.username != 'admin').delete()
        db.session.commit()
        
        # Create sample supervisors
        print("Creating supervisors...")
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
                password=generate_password_hash('supervisor123', method='pbkdf2:sha256'),
                user_type='supervisor',
                cdl=sup_data['cdl'],
                gender=sup_data['gender'],
                nationality=sup_data['nationality'],
                joined_on=int(time.time())
            )
            supervisors.append(supervisor)
            db.session.add(supervisor)
        
        # Create sample students
        print("Creating students...")
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
                password=generate_password_hash('student123', method='pbkdf2:sha256'),
                user_type='student',
                cdl=std_data['cdl'],
                gender=std_data['gender'],
                nationality=std_data['nationality'],
                joined_on=int(time.time())
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
        
        print("Database seeding completed successfully!")
        print(f"Created:")
        print(f"  - 1 admin user (username: admin, password: test)")
        print(f"  - {len(supervisors)} supervisors (password: supervisor123)")
        print(f"  - {len(students)} students (password: student123)")
        print(f"  - {len(theses)} theses (5 assigned, 2 available)")
        print(f"  - Thesis statuses and tags")

if __name__ == '__main__':
    seed_database()