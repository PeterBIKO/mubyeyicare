from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import enum

db = SQLAlchemy()

class UserRole(enum.Enum):
    ADMIN = 'admin'
    DOCTOR = 'doctor'
    NURSE = 'nurse'
    CHW = 'chw'
    MOTHER = 'mother'
    PATIENT = 'patient'

class WoundStatus(enum.Enum):
    EXCELLENT = 'excellent'
    GOOD = 'good'
    FAIR = 'fair'
    POOR = 'poor'
    INFECTED = 'infected'

class User(UserMixin, db.Model):
    """User model for healthcare providers and patients"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.PATIENT, nullable=False)
    phone = db.Column(db.String(20))
    location = db.Column(db.String(200))   # CHW service area (e.g. "Gasabo/Kinyinya")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patients = db.relationship('Patient', backref='primary_doctor', lazy='dynamic', foreign_keys='Patient.primary_doctor_id')
    follow_ups = db.relationship('FollowUp', backref='created_by', lazy='dynamic')
    sent_messages = db.relationship('Message', backref='sender', lazy='dynamic', foreign_keys='Message.sender_id')

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)

    def get_full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f'<User {self.username}>'


class Patient(db.Model):
    """Patient model for post-cesarean care tracking"""
    id = db.Column(db.Integer, primary_key=True)
    mrn = db.Column(db.String(50), unique=True, nullable=False)  # Medical Record Number
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    
    # Cesarean surgery details
    surgery_date = db.Column(db.Date, nullable=False)
    surgery_type = db.Column(db.String(100))  # e.g., "Primary Cesarean", "VBAC attempt"
    surgeon_name = db.Column(db.String(100))
    incision_type = db.Column(db.String(50))  # e.g., "Pfannenstiel", "Classical"
    
    # Location (used for CHW filtering)
    location = db.Column(db.String(200))   # e.g. "Gasabo/Kinyinya"

    # Care details
    primary_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    admission_date = db.Column(db.DateTime, default=datetime.utcnow)
    discharge_date = db.Column(db.DateTime)
    expected_follow_up_end_date = db.Column(db.Date)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    follow_ups = db.relationship('FollowUp', backref='patient', lazy='dynamic', cascade='all, delete-orphan')
    wound_assessments = db.relationship('WoundAssessment', backref='patient', lazy='dynamic', cascade='all, delete-orphan')
    medications = db.relationship('MedicationLog', backref='patient', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='patient', lazy='dynamic', cascade='all, delete-orphan')
    user = db.relationship('User', backref='patient_profile', foreign_keys=[user_id], uselist=False)

    def get_full_name(self):
        """Get patient's full name"""
        return f"{self.first_name} {self.last_name}"

    def get_age(self):
        """Calculate patient's age"""
        today = datetime.utcnow().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def days_post_surgery(self):
        """Calculate days since surgery"""
        return (datetime.utcnow().date() - self.surgery_date).days

    def __repr__(self):
        return f'<Patient {self.mrn} - {self.get_full_name()}>'


class FollowUp(db.Model):
    """Follow-up appointment/check-in record"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    follow_up_date = db.Column(db.DateTime, nullable=False)
    follow_up_type = db.Column(db.String(50), nullable=False)  # e.g., "In-person", "Telemedicine", "Phone"
    visit_location = db.Column(db.String(255))  # e.g., "OPD", "Home"
    
    # Clinical notes
    notes = db.Column(db.Text)
    vitals_recorded = db.Column(db.Boolean, default=False)
    
    # Status
    is_completed = db.Column(db.Boolean, default=False)
    completion_date = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    wound_assessment = db.relationship('WoundAssessment', backref='follow_up', uselist=False, cascade='all, delete-orphan')
    vital_signs = db.relationship('VitalSigns', backref='follow_up', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<FollowUp Patient:{self.patient_id} Date:{self.follow_up_date}>'


class WoundAssessment(db.Model):
    """Wound assessment record"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    follow_up_id = db.Column(db.Integer, db.ForeignKey('follow_up.id'))
    
    assessment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Wound characteristics
    status = db.Column(db.Enum(WoundStatus), default=WoundStatus.GOOD)
    redness_present = db.Column(db.Boolean, default=False)
    swelling_present = db.Column(db.Boolean, default=False)
    discharge_present = db.Column(db.Boolean, default=False)
    discharge_type = db.Column(db.String(100))  # e.g., "Serosanguinous", "Purulent"
    dehiscence_present = db.Column(db.Boolean, default=False)
    infection_signs = db.Column(db.Boolean, default=False)
    
    # Measurements
    incision_length = db.Column(db.Float)  # in cm
    wound_depth = db.Column(db.Float)  # in mm
    
    # General observations
    pain_level = db.Column(db.Integer)  # 0-10 scale
    healing_progress = db.Column(db.String(50))  # e.g., "On track", "Delayed"
    observations = db.Column(db.Text)
    
    # Recommendations
    dressing_change_needed = db.Column(db.Boolean, default=False)
    dressing_type = db.Column(db.String(100))
    antibiotic_prescribed = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<WoundAssessment Patient:{self.patient_id} Status:{self.status}>'


class VitalSigns(db.Model):
    """Vital signs record"""
    id = db.Column(db.Integer, primary_key=True)
    follow_up_id = db.Column(db.Integer, db.ForeignKey('follow_up.id'), nullable=False)
    
    recorded_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Vital signs measurements
    blood_pressure_systolic = db.Column(db.Integer)
    blood_pressure_diastolic = db.Column(db.Integer)
    heart_rate = db.Column(db.Integer)
    temperature = db.Column(db.Float)  # in Celsius
    respiratory_rate = db.Column(db.Integer)
    oxygen_saturation = db.Column(db.Float)  # in percentage
    
    # Additional
    weight = db.Column(db.Float)  # in kg
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<VitalSigns FollowUp:{self.follow_up_id} Date:{self.recorded_date}>'


class MedicationLog(db.Model):
    """Medication tracking log"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    
    medication_name = db.Column(db.String(255), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)  # e.g., "500mg"
    frequency = db.Column(db.String(100), nullable=False)  # e.g., "Every 8 hours"
    route = db.Column(db.String(50), nullable=False)  # e.g., "Oral", "IV"
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    indication = db.Column(db.String(255))  # Why prescribed
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<MedicationLog Patient:{self.patient_id} Drug:{self.medication_name}>'


class Message(db.Model):
    """Patient-provider chat messages"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    attachment_filename = db.Column(db.String(255))
    attachment_type = db.Column(db.String(100))
    attachment_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Message Patient:{self.patient_id} Sender:{self.sender_id}>'


class Alert(db.Model):
    """Alert system for critical observations"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    assigned_hcp_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    alert_type = db.Column(db.String(100), nullable=False)
    severity = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)

    is_resolved = db.Column(db.Boolean, default=False)
    resolution_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    assigned_hcp = db.relationship('User', foreign_keys=[assigned_hcp_id])
    alert_patient = db.relationship('Patient', foreign_keys=[patient_id], backref='alerts')

    def __repr__(self):
        return f'<Alert Patient:{self.patient_id} Type:{self.alert_type}>'


# ── Appointment Requests ──────────────────────────────────────────────────────

class AppointmentStatus(enum.Enum):
    PENDING   = 'pending'
    APPROVED  = 'approved'
    REJECTED  = 'rejected'
    RESCHEDULED = 'rescheduled'


class AppointmentRequest(db.Model):
    """Patient-initiated appointment requests managed by admin/HCP."""
    id = db.Column(db.Integer, primary_key=True)
    patient_id      = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    preferred_date  = db.Column(db.DateTime, nullable=False)
    reason          = db.Column(db.Text)
    status = db.Column(db.Enum(AppointmentStatus), default=AppointmentStatus.PENDING, nullable=False)
    assigned_hcp_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    scheduled_date  = db.Column(db.DateTime)
    admin_notes     = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient      = db.relationship('Patient', backref='appointment_requests', foreign_keys=[patient_id])
    requested_by = db.relationship('User', foreign_keys=[requested_by_id])
    assigned_hcp = db.relationship('User', foreign_keys=[assigned_hcp_id])

    def __repr__(self):
        return f'<AppointmentRequest Patient:{self.patient_id} Status:{self.status.value}>'


# ── Public Message Wall ───────────────────────────────────────────────────────

class PublicMessage(db.Model):
    """Public HCP/patient wall posts (visible to all authenticated users)."""
    id         = db.Column(db.Integer, primary_key=True)
    author_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    attachment_url  = db.Column(db.String(255))
    attachment_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author  = db.relationship('User', backref='wall_posts')
    replies = db.relationship('PublicMessageReply', backref='post',
                              lazy='dynamic', cascade='all, delete-orphan',
                              order_by='PublicMessageReply.created_at')

    def __repr__(self):
        return f'<PublicMessage by User:{self.author_id}>'


class PublicMessageReply(db.Model):
    """Replies to public wall posts."""
    id         = db.Column(db.Integer, primary_key=True)
    post_id    = db.Column(db.Integer, db.ForeignKey('public_message.id'), nullable=False)
    author_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', backref='wall_replies')

    def __repr__(self):
        return f'<PublicMessageReply Post:{self.post_id} by User:{self.author_id}>'


# ── Education Content ─────────────────────────────────────────────────────────

class EducationStatus(enum.Enum):
    DRAFT    = 'draft'
    PENDING  = 'pending'   # submitted by HCP, awaiting admin approval
    APPROVED = 'approved'
    REJECTED = 'rejected'


class EducationContent(db.Model):
    """Educational content — created by HCPs or admin, approved and published by admin."""
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(255), nullable=False)
    summary    = db.Column(db.String(500))           # short abstract shown on cards
    body       = db.Column(db.Text, nullable=False)
    category   = db.Column(db.String(100))
    tags       = db.Column(db.String(300))           # comma-separated tags
    content_type = db.Column(db.String(30), default='article')  # article|video|infographic|guideline|quiz
    thumbnail_url = db.Column(db.String(300))        # cover image URL
    video_url     = db.Column(db.String(300))        # external video URL (YouTube/Vimeo)
    reading_time  = db.Column(db.Integer, default=5) # estimated minutes
    view_count    = db.Column(db.Integer, default=0)
    is_featured   = db.Column(db.Boolean, default=False)
    target_audience = db.Column(db.String(20), default='all')   # all|patients|hcps
    author_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status     = db.Column(db.Enum(EducationStatus), default=EducationStatus.DRAFT, nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    published_to_patients = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author      = db.relationship('User', foreign_keys=[author_id], backref='education_posts')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])
    bookmarks   = db.relationship('EducationBookmark', backref='content', lazy='dynamic', cascade='all, delete-orphan')

    def tag_list(self):
        return [t.strip() for t in (self.tags or '').split(',') if t.strip()]

    def reading_time_label(self):
        mins = self.reading_time or 5
        return f'{mins} min read'

    def __repr__(self):
        return f'<EducationContent {self.title[:30]} type:{self.content_type} status:{self.status.value}>'


class EducationBookmark(db.Model):
    """Users can bookmark education articles to read later."""
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content_id = db.Column(db.Integer, db.ForeignKey('education_content.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='education_bookmarks')
    __table_args__ = (db.UniqueConstraint('user_id', 'content_id', name='uq_edu_bookmark'),)


# ── Broadcast Messages ────────────────────────────────────────────────────────

class Notification(db.Model):
    """In-app notifications for appointment events, alerts, and reminders."""
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title       = db.Column(db.String(200), nullable=False)
    message     = db.Column(db.Text, nullable=False)
    notif_type  = db.Column(db.String(30), default='info')   # appointment | alert | reminder | info
    link        = db.Column(db.String(255))                  # URL to navigate to on click
    is_read     = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    recipient = db.relationship('User', backref='notifications', foreign_keys=[user_id])

    def __repr__(self):
        return f'<Notification user:{self.user_id} type:{self.notif_type} read:{self.is_read}>'


class BroadcastMessage(db.Model):
    """Admin broadcast — targets: 'all', 'patients', 'hcps', or 'user:<id>'."""
    id         = db.Column(db.Integer, primary_key=True)
    sender_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    target     = db.Column(db.String(50), nullable=False, default='all')
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender      = db.relationship('User', foreign_keys=[sender_id], backref='broadcasts')
    target_user = db.relationship('User', foreign_keys=[target_user_id])

    def __repr__(self):
        return f'<BroadcastMessage sender:{self.sender_id} target:{self.target}>'
