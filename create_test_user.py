#!/usr/bin/env python3
from crm import create_app
from crm.extensions import db
from crm.models.user import User
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    # Check if admin exists
    admin = User.query.filter_by(email="admin@lexflow.test").first()
    if not admin:
        admin = User(
            email="admin@lexflow.test",
            password_hash=generate_password_hash("Admin@12345", method="pbkdf2:sha256"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()
        print("✓ Admin user created: admin@lexflow.test / Admin@12345")
    else:
        print("✓ Admin user already exists")
    
    # Create test lawyer
    lawyer = User.query.filter_by(email="lawyer@lexflow.test").first()
    if not lawyer:
        lawyer = User(
            email="lawyer@lexflow.test",
            password_hash=generate_password_hash("Lawyer@12345", method="pbkdf2:sha256"),
            role="lawyer"
        )
        db.session.add(lawyer)
        db.session.commit()
        print("✓ Test lawyer created: lawyer@lexflow.test / Lawyer@12345")
    else:
        print("✓ Test lawyer already exists")
    
    # Count users
    count = User.query.count()
    print(f"✓ Total users in database: {count}")
