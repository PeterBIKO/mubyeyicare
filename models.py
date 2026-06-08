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
    
    alert_type = db.Column(db.String(100), nullable=False)  # e.g., "Infection Risk", "Delayed Healing"
    severity = db.Column(db.String(50), nullable=False)  # e.g., "Low", "Medium", "High", "Critical"
    message = db.Column(db.Text, nullable=False)
    
    is_resolved = db.Column(db.Boolean, default=False)
    resolution_notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Alert Patient:{self.patient_id} Type:{self.alert_type}>'
