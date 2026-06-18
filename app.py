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
    from routes.notifications import notifications_bp
    from routes.education import education_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(follow_ups_bp)
    app.register_blueprint(assessments_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(wall_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(education_bp)

    @app.route('/')
    def home():
        return redirect(url_for('dashboard.index'))

    # Inject unread notification count into every template
    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        from models import Notification
        if current_user.is_authenticated:
            unread = Notification.query.filter_by(
                user_id=current_user.id, is_read=False).count()
        else:
            unread = 0
        return {'unread_notifications': unread}

    # ── Language / i18n ─────────────────────────────────────────────────────
    @app.route('/set-lang/<lang_code>', methods=['POST', 'GET'])
    def set_lang(lang_code):
        from flask import session, request as req
        if lang_code in ('en', 'rw'):
            session['lang'] = lang_code
        next_url = req.args.get('next') or req.referrer or '/'
        from flask import redirect
        return redirect(next_url)

    @app.context_processor
    def inject_language():
        from flask import session
        from translations.rw import KINYARWANDA

        lang = session.get('lang', 'en')

        def tr(text):
            """Return translated string if Kinyarwanda is active, else original."""
            if lang == 'rw':
                return KINYARWANDA.get(text, text)
            return text

        return {'tr': tr, 'current_lang': lang}
    
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

        # notification table is created by db.create_all() above; no manual migration needed

        # education_content: new columns added in v2
        if "education_content" in inspector.get_table_names():
            existing_edu = {col["name"] for col in inspector.get_columns("education_content")}
            new_edu_cols = [
                ("summary",          "VARCHAR(500)"),
                ("tags",             "VARCHAR(300)"),
                ("content_type",     "VARCHAR(30) DEFAULT 'article'"),
                ("thumbnail_url",    "VARCHAR(300)"),
                ("video_url",        "VARCHAR(300)"),
                ("reading_time",     "INTEGER DEFAULT 5"),
                ("view_count",       "INTEGER DEFAULT 0"),
                ("is_featured",      "BOOLEAN DEFAULT 0"),
                ("target_audience",  "VARCHAR(20) DEFAULT 'all'"),
            ]
            for col_name, col_def in new_edu_cols:
                if col_name not in existing_edu:
                    with db.engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE education_content ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
    
    return app
