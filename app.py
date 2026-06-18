from flask import Flask, redirect, url_for
from flask_login import LoginManager
from sqlalchemy import inspect, text
from models import db, User
from config import config
import os

def create_app(config_name=None):
    """Application factory function"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.patients import patients_bp
    from routes.follow_ups import follow_ups_bp
    from routes.assessments import assessments_bp
    from routes.chat import chat_bp
    from routes.admin import admin_bp
    from routes.appointments import appointments_bp
    from routes.wall import wall_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(follow_ups_bp)
    app.register_blueprint(assessments_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(wall_bp)

    @app.route('/')
    def home():
        return redirect(url_for('dashboard.index'))
    
    # Create database tables and apply schema upgrades
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)

        # message table: attachment columns
        if "message" in inspector.get_table_names():
            existing = {col["name"] for col in inspector.get_columns("message")}
            for name, col_type in [
                ("attachment_filename", "VARCHAR(255)"),
                ("attachment_type", "VARCHAR(100)"),
                ("attachment_url", "VARCHAR(255)")
            ]:
                if name not in existing:
                    with db.engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE message ADD COLUMN {name} {col_type}"))
                        conn.commit()

        # patient table: user_id + location
        if "patient" in inspector.get_table_names():
            existing_patient = {col["name"] for col in inspector.get_columns("patient")}
            for name, col_type in [
                ("user_id", "INTEGER"),
                ("location", "VARCHAR(200)")
            ]:
                if name not in existing_patient:
                    with db.engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE patient ADD COLUMN {name} {col_type}"))
                        conn.commit()

        # user table: location
        if "user" in inspector.get_table_names():
            existing_user = {col["name"] for col in inspector.get_columns("user")}
            if "location" not in existing_user:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE user ADD COLUMN location VARCHAR(200)"))
                    conn.commit()

        # alert table: assigned_hcp_id
        if "alert" in inspector.get_table_names():
            existing_alert = {col["name"] for col in inspector.get_columns("alert")}
            if "assigned_hcp_id" not in existing_alert:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE alert ADD COLUMN assigned_hcp_id INTEGER REFERENCES user(id)"))
                    conn.commit()
    
    return app
