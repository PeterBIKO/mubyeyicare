from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from models import db, User, UserRole, Patient
from functools import wraps

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def admin_required(f):
    """Decorator for admin-only routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_nurse_required(f):
    """Decorator for provider routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in [UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW, UserRole.ADMIN]:
            flash('Healthcare provider access required.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=request.form.get('remember'))
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration (admin only)"""
    if not current_user.is_authenticated or current_user.role != UserRole.ADMIN:
        flash('Only admins can register new users.', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')
        phone = request.form.get('phone')
        location = request.form.get('location', '').strip()
        
        # Validation
        if not all([username, email, first_name, last_name, password, role]):
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.register'))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('auth.register'))
        
        # Create new user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=UserRole(role),
            phone=phone,
            location=location or None
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        if user.role in [UserRole.PATIENT, UserRole.MOTHER]:
            patient = Patient.query.filter(
                (Patient.email == email) | (Patient.phone == phone)
            ).first()
            if patient:
                patient.user_id = user.id
                db.session.commit()

        flash(f'User {username} registered successfully.', 'success')
        return redirect(url_for('dashboard.index'))
    
    return render_template('auth/register.html', roles=UserRole)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """View user profile"""
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    current_user.first_name = request.form.get('first_name', current_user.first_name)
    current_user.last_name = request.form.get('last_name', current_user.last_name)
    current_user.phone = request.form.get('phone', current_user.phone)
    
    db.session.commit()
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('auth.profile'))

@auth_bp.route('/link-patient', methods=['GET', 'POST'])
@login_required
def link_patient():
    """Link a patient user account to an existing patient record"""
    if current_user.role not in [UserRole.PATIENT, UserRole.MOTHER]:
        flash('Only patient and mother accounts can link to patient records.', 'error')
        return redirect(url_for('dashboard.index'))

    existing_patient = Patient.query.filter_by(user_id=current_user.id).first()
    if existing_patient:
        flash('Your account is already linked to a patient record.', 'info')
        return redirect(url_for('auth.profile'))

    if request.method == 'POST':
        mrn = request.form.get('mrn', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        if not mrn and not email and not phone:
            flash('Please enter MRN, email, or phone to link your patient record.', 'error')
            return redirect(url_for('auth.link_patient'))

        patient = None
        if mrn:
            patient = Patient.query.filter_by(mrn=mrn).first()
        if not patient and email:
            patient = Patient.query.filter_by(email=email).first()
        if not patient and phone:
            patient = Patient.query.filter_by(phone=phone).first()

        if not patient:
            flash('No matching patient record found. Please verify your details.', 'error')
            return redirect(url_for('auth.link_patient'))

        if patient.user_id and patient.user_id != current_user.id:
            flash('This patient record is already linked to another account.', 'error')
            return redirect(url_for('auth.link_patient'))

        patient.user_id = current_user.id
        db.session.commit()

        flash('Patient account successfully linked to your profile.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/link_patient.html')
