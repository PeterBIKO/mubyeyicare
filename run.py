#!/usr/bin/env python
"""
Main entry point for the Post-Cesarean Wound Care System application
"""

import os
from app import create_app, db
from models import User, UserRole
from datetime import datetime

app = create_app(os.environ.get('FLASK_ENV', 'development'))

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'UserRole': UserRole
    }

@app.cli.command()
def init_db():
    """Initialize the database with sample data"""
    db.create_all()
    
    # Check if admin user exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            first_name='System',
            last_name='Administrator',
            role=UserRole.ADMIN
        )
        admin.set_password('admin123')
        
        db.session.add(admin)
        db.session.commit()
        
        print("✓ Database initialized with admin user")
        print("  Username: admin")
        print("  Password: admin123")
    else:
        print("✓ Database already initialized")

@app.cli.command()
def create_admin():
    """Create a new admin user"""
    print("Create Admin User")
    username = input("Username: ").strip()
    
    if User.query.filter_by(username=username).first():
        print("Error: Username already exists")
        return
    
    email = input("Email: ").strip()
    first_name = input("First Name: ").strip()
    last_name = input("Last Name: ").strip()
    password = input("Password: ").strip()
    
    if not all([username, email, first_name, last_name, password]):
        print("Error: All fields are required")
        return
    
    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=UserRole.ADMIN
    )
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    print(f"✓ Admin user '{username}' created successfully")

if __name__ == '__main__':
    app.run(debug=True)
