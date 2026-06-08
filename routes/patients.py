from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from models import db, Patient, User, UserRole, FollowUp, WoundAssessment
from datetime import datetime
from routes.auth import doctor_nurse_required

patients_bp = Blueprint('patients', __name__, url_prefix='/patients')

@patients_bp.route('/')
@login_required
@doctor_nurse_required
def list_patients():
    """List all patients"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Patient.query
    
    if search:
        query = query.filter(
            (Patient.first_name.ilike(f'%{search}%')) |
            (Patient.last_name.ilike(f'%{search}%')) |
            (Patient.mrn.ilike(f'%{search}%')) |
            (Patient.email.ilike(f'%{search}%'))
        )
    
    if current_user.role not in [UserRole.ADMIN]:
        query = query.filter_by(primary_doctor_id=current_user.id)
    
    patients = query.paginate(page=page, per_page=10)
    
    return render_template('patients/list.html', patients=patients, search=search)

@patients_bp.route('/create', methods=['GET', 'POST'])
@login_required
@doctor_nurse_required
def create_patient():
    """Create new patient record"""
    if request.method == 'POST':
        mrn = request.form.get('mrn')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date()
        gender = request.form.get('gender')
        phone = request.form.get('phone')
        email = request.form.get('email')
        surgery_date = datetime.strptime(request.form.get('surgery_date'), '%Y-%m-%d').date()
        surgery_type = request.form.get('surgery_type')
        surgeon_name = request.form.get('surgeon_name')
        incision_type = request.form.get('incision_type')
        
        # Validation
        if Patient.query.filter_by(mrn=mrn).first():
            flash('Patient with this MRN already exists.', 'error')
            return redirect(url_for('patients.create_patient'))
        
        # Create patient
        patient = Patient(
            mrn=mrn,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=gender,
            phone=phone,
            email=email,
            surgery_date=surgery_date,
            surgery_type=surgery_type,
            surgeon_name=surgeon_name,
            incision_type=incision_type,
            primary_doctor_id=current_user.id
        )
        existing_user = User.query.filter(
            (User.email == email) | (User.phone == phone)
        ).first()
        if existing_user and existing_user.role == UserRole.PATIENT:
            patient.user_id = existing_user.id
        
        db.session.add(patient)
        db.session.commit()
        
        flash(f'Patient {first_name} {last_name} created successfully.', 'success')
        return redirect(url_for('patients.view_patient', patient_id=patient.id))
    
    return render_template('patients/create.html')

@patients_bp.route('/<int:patient_id>')
@login_required
@doctor_nurse_required
def view_patient(patient_id):
    """View patient details"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to view this patient.', 'error')
        return redirect(url_for('dashboard.index'))
    
    follow_ups = patient.follow_ups.order_by(FollowUp.follow_up_date.desc()).all()
    assessments = patient.wound_assessments.order_by(WoundAssessment.assessment_date.desc()).all()
    medications = patient.medications.filter_by(is_active=True).all()
    
    return render_template('patients/view.html',
                         patient=patient,
                         follow_ups=follow_ups,
                         assessments=assessments,
                         medications=medications)

@patients_bp.route('/<int:patient_id>/edit', methods=['GET', 'POST'])
@login_required
@doctor_nurse_required
def edit_patient(patient_id):
    """Edit patient record"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to edit this patient.', 'error')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        patient.first_name = request.form.get('first_name', patient.first_name)
        patient.last_name = request.form.get('last_name', patient.last_name)
        patient.phone = request.form.get('phone', patient.phone)
        patient.email = request.form.get('email', patient.email)
        patient.surgery_type = request.form.get('surgery_type', patient.surgery_type)
        patient.surgeon_name = request.form.get('surgeon_name', patient.surgeon_name)
        patient.incision_type = request.form.get('incision_type', patient.incision_type)
        
        discharge_date_str = request.form.get('discharge_date')
        if discharge_date_str:
            patient.discharge_date = datetime.strptime(discharge_date_str, '%Y-%m-%d')
        
        patient.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Patient record updated successfully.', 'success')
        return redirect(url_for('patients.view_patient', patient_id=patient.id))
    
    return render_template('patients/edit.html', patient=patient)

@patients_bp.route('/<int:patient_id>/discharge', methods=['POST'])
@login_required
@doctor_nurse_required
def discharge_patient(patient_id):
    """Discharge patient from follow-up"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to discharge this patient.', 'error')
        return redirect(url_for('dashboard.index'))
    
    patient.is_active = False
    patient.discharge_date = datetime.utcnow()
    patient.updated_at = datetime.utcnow()
    
    db.session.commit()
    flash(f'Patient {patient.get_full_name()} discharged successfully.', 'success')
    return redirect(url_for('patients.list_patients'))

@patients_bp.route('/api/search')
@login_required
@doctor_nurse_required
def search_patients():
    """API endpoint for patient search (AJAX)"""
    query = request.args.get('q', '')
    
    patients = Patient.query.filter(
        (Patient.first_name.ilike(f'%{query}%')) |
        (Patient.last_name.ilike(f'%{query}%')) |
        (Patient.mrn.ilike(f'%{query}%'))
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'mrn': p.mrn,
        'name': p.get_full_name()
    } for p in patients])
