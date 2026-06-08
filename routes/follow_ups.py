from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, FollowUp, Patient, VitalSigns, UserRole
from datetime import datetime
from routes.auth import doctor_nurse_required

follow_ups_bp = Blueprint('follow_ups', __name__, url_prefix='/follow-ups')

@follow_ups_bp.route('/patient/<int:patient_id>')
@login_required
@doctor_nurse_required
def patient_follow_ups(patient_id):
    """View all follow-ups for a patient"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to view this patient.', 'error')
        return redirect(url_for('dashboard.index'))
    
    follow_ups = patient.follow_ups.order_by(db.desc(FollowUp.follow_up_date)).all()
    
    return render_template('follow_ups/patient_follow_ups.html',
                         patient=patient,
                         follow_ups=follow_ups)

@follow_ups_bp.route('/create/<int:patient_id>', methods=['GET', 'POST'])
@login_required
@doctor_nurse_required
def create_follow_up(patient_id):
    """Schedule a new follow-up"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to manage follow-ups for this patient.', 'error')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        follow_up_date_str = request.form.get('follow_up_date')
        follow_up_time_str = request.form.get('follow_up_time', '09:00')
        follow_up_type = request.form.get('follow_up_type')
        visit_location = request.form.get('visit_location', '')
        notes = request.form.get('notes', '')
        
        # Parse datetime
        follow_up_datetime = datetime.strptime(
            f"{follow_up_date_str} {follow_up_time_str}",
            '%Y-%m-%d %H:%M'
        )
        
        follow_up = FollowUp(
            patient_id=patient_id,
            created_by_id=current_user.id,
            follow_up_date=follow_up_datetime,
            follow_up_type=follow_up_type,
            visit_location=visit_location,
            notes=notes
        )
        
        db.session.add(follow_up)
        db.session.commit()
        
        flash('Follow-up scheduled successfully.', 'success')
        return redirect(url_for('follow_ups.view_follow_up', follow_up_id=follow_up.id))
    
    return render_template('follow_ups/create.html', patient=patient)

@follow_ups_bp.route('/<int:follow_up_id>')
@login_required
def view_follow_up(follow_up_id):
    """View follow-up details"""
    follow_up = FollowUp.query.get_or_404(follow_up_id)
    
    # Check authorization
    patient = follow_up.patient
    if current_user.role == UserRole.PATIENT:
        if not (patient.user_id == current_user.id or patient.email == current_user.email or patient.phone == current_user.phone):
            flash('You do not have permission to view this follow-up.', 'error')
            return redirect(url_for('dashboard.index'))
    elif current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to view this follow-up.', 'error')
        return redirect(url_for('dashboard.index'))
    
    return render_template('follow_ups/view.html',
                         follow_up=follow_up,
                         patient=patient)

@follow_ups_bp.route('/<int:follow_up_id>/complete', methods=['GET', 'POST'])
@login_required
@doctor_nurse_required
def complete_follow_up(follow_up_id):
    """Complete a follow-up visit"""
    follow_up = FollowUp.query.get_or_404(follow_up_id)
    
    # Check authorization
    patient = follow_up.patient
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to complete this follow-up.', 'error')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        notes = request.form.get('notes', '')
        vitals_recorded = request.form.get('vitals_recorded') == 'on'
        
        follow_up.notes = notes
        follow_up.vitals_recorded = vitals_recorded
        follow_up.is_completed = True
        follow_up.completion_date = datetime.utcnow()
        
        # Record vital signs if provided
        if vitals_recorded:
            vitals = VitalSigns(
                follow_up_id=follow_up_id,
                blood_pressure_systolic=request.form.get('blood_pressure_systolic', type=int),
                blood_pressure_diastolic=request.form.get('blood_pressure_diastolic', type=int),
                heart_rate=request.form.get('heart_rate', type=int),
                temperature=request.form.get('temperature', type=float),
                respiratory_rate=request.form.get('respiratory_rate', type=int),
                oxygen_saturation=request.form.get('oxygen_saturation', type=float),
                weight=request.form.get('weight', type=float)
            )
            db.session.add(vitals)
        
        db.session.commit()
        
        flash('Follow-up completed successfully.', 'success')
        return redirect(url_for('follow_ups.view_follow_up', follow_up_id=follow_up.id))
    
    return render_template('follow_ups/complete.html',
                         follow_up=follow_up,
                         patient=patient)

@follow_ups_bp.route('/<int:follow_up_id>/edit', methods=['GET', 'POST'])
@login_required
@doctor_nurse_required
def edit_follow_up(follow_up_id):
    """Edit follow-up details"""
    follow_up = FollowUp.query.get_or_404(follow_up_id)
    
    # Check authorization
    patient = follow_up.patient
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to edit this follow-up.', 'error')
        return redirect(url_for('dashboard.index'))
    
    if follow_up.is_completed:
        flash('Cannot edit a completed follow-up.', 'error')
        return redirect(url_for('follow_ups.view_follow_up', follow_up_id=follow_up.id))
    
    if request.method == 'POST':
        follow_up_date_str = request.form.get('follow_up_date')
        follow_up_time_str = request.form.get('follow_up_time', '09:00')
        follow_up_type = request.form.get('follow_up_type')
        visit_location = request.form.get('visit_location', '')
        notes = request.form.get('notes', '')
        
        follow_up.follow_up_date = datetime.strptime(
            f"{follow_up_date_str} {follow_up_time_str}",
            '%Y-%m-%d %H:%M'
        )
        follow_up.follow_up_type = follow_up_type
        follow_up.visit_location = visit_location
        follow_up.notes = notes
        
        db.session.commit()
        
        flash('Follow-up updated successfully.', 'success')
        return redirect(url_for('follow_ups.view_follow_up', follow_up_id=follow_up.id))
    
    return render_template('follow_ups/edit.html',
                         follow_up=follow_up,
                         patient=patient)
