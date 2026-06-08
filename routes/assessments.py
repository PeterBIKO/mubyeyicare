from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, WoundAssessment, Patient, FollowUp, Alert, WoundStatus, UserRole
from datetime import datetime
from routes.auth import doctor_nurse_required

assessments_bp = Blueprint('assessments', __name__, url_prefix='/assessments')

@assessments_bp.route('/patient/<int:patient_id>')
@login_required
@doctor_nurse_required
def patient_assessments(patient_id):
    """View all wound assessments for a patient"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to view this patient.', 'error')
        return redirect(url_for('dashboard.index'))
    
    assessments = patient.wound_assessments.order_by(db.desc(WoundAssessment.assessment_date)).all()
    
    return render_template('assessments/patient_assessments.html',
                         patient=patient,
                         assessments=assessments)

@assessments_bp.route('/create/<int:patient_id>', methods=['GET', 'POST'])
@login_required
@doctor_nurse_required
def create_assessment(patient_id):
    """Create a new wound assessment"""
    patient = Patient.query.get_or_404(patient_id)
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to assess this patient.', 'error')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        status = request.form.get('status')
        redness_present = request.form.get('redness_present') == 'on'
        swelling_present = request.form.get('swelling_present') == 'on'
        discharge_present = request.form.get('discharge_present') == 'on'
        discharge_type = request.form.get('discharge_type', '')
        dehiscence_present = request.form.get('dehiscence_present') == 'on'
        infection_signs = request.form.get('infection_signs') == 'on'
        incision_length = request.form.get('incision_length', type=float)
        wound_depth = request.form.get('wound_depth', type=float)
        pain_level = request.form.get('pain_level', type=int)
        healing_progress = request.form.get('healing_progress', '')
        observations = request.form.get('observations', '')
        dressing_change_needed = request.form.get('dressing_change_needed') == 'on'
        dressing_type = request.form.get('dressing_type', '')
        antibiotic_prescribed = request.form.get('antibiotic_prescribed') == 'on'
        follow_up_id = request.form.get('follow_up_id', type=int)
        
        assessment = WoundAssessment(
            patient_id=patient_id,
            follow_up_id=follow_up_id,
            status=WoundStatus(status),
            redness_present=redness_present,
            swelling_present=swelling_present,
            discharge_present=discharge_present,
            discharge_type=discharge_type,
            dehiscence_present=dehiscence_present,
            infection_signs=infection_signs,
            incision_length=incision_length,
            wound_depth=wound_depth,
            pain_level=pain_level,
            healing_progress=healing_progress,
            observations=observations,
            dressing_change_needed=dressing_change_needed,
            dressing_type=dressing_type,
            antibiotic_prescribed=antibiotic_prescribed
        )
        
        db.session.add(assessment)
        
        # Create alerts if needed
        if infection_signs or discharge_present or dehiscence_present:
            alert_type = 'Infection Risk' if infection_signs else 'Abnormal Discharge' if discharge_present else 'Wound Dehiscence'
            severity = 'High' if infection_signs else 'Medium'
            message = f'Alert for {patient.get_full_name()}: {alert_type} detected during assessment.'
            
            alert = Alert(
                patient_id=patient_id,
                alert_type=alert_type,
                severity=severity,
                message=message
            )
            db.session.add(alert)
        
        db.session.commit()
        
        flash('Wound assessment created successfully.', 'success')
        return redirect(url_for('assessments.view_assessment', assessment_id=assessment.id))
    
    # Get follow-ups for this patient
    follow_ups = patient.follow_ups.filter_by(is_completed=False).all()
    
    return render_template('assessments/create.html',
                         patient=patient,
                         follow_ups=follow_ups,
                         statuses=WoundStatus)

@assessments_bp.route('/<int:assessment_id>')
@login_required
@doctor_nurse_required
def view_assessment(assessment_id):
    """View wound assessment details"""
    assessment = WoundAssessment.query.get_or_404(assessment_id)
    patient = assessment.patient
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to view this assessment.', 'error')
        return redirect(url_for('dashboard.index'))
    
    return render_template('assessments/view.html',
                         assessment=assessment,
                         patient=patient)

@assessments_bp.route('/<int:assessment_id>/edit', methods=['GET', 'POST'])
@login_required
@doctor_nurse_required
def edit_assessment(assessment_id):
    """Edit wound assessment"""
    assessment = WoundAssessment.query.get_or_404(assessment_id)
    patient = assessment.patient
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to edit this assessment.', 'error')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        assessment.status = WoundStatus(request.form.get('status'))
        assessment.redness_present = request.form.get('redness_present') == 'on'
        assessment.swelling_present = request.form.get('swelling_present') == 'on'
        assessment.discharge_present = request.form.get('discharge_present') == 'on'
        assessment.discharge_type = request.form.get('discharge_type', '')
        assessment.dehiscence_present = request.form.get('dehiscence_present') == 'on'
        assessment.infection_signs = request.form.get('infection_signs') == 'on'
        assessment.incision_length = request.form.get('incision_length', type=float)
        assessment.wound_depth = request.form.get('wound_depth', type=float)
        assessment.pain_level = request.form.get('pain_level', type=int)
        assessment.healing_progress = request.form.get('healing_progress', '')
        assessment.observations = request.form.get('observations', '')
        assessment.dressing_change_needed = request.form.get('dressing_change_needed') == 'on'
        assessment.dressing_type = request.form.get('dressing_type', '')
        assessment.antibiotic_prescribed = request.form.get('antibiotic_prescribed') == 'on'
        assessment.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Assessment updated successfully.', 'success')
        return redirect(url_for('assessments.view_assessment', assessment_id=assessment.id))
    
    follow_ups = patient.follow_ups.all()
    
    return render_template('assessments/edit.html',
                         assessment=assessment,
                         patient=patient,
                         follow_ups=follow_ups,
                         statuses=WoundStatus)

@assessments_bp.route('/<int:assessment_id>/delete', methods=['POST'])
@login_required
@doctor_nurse_required
def delete_assessment(assessment_id):
    """Delete wound assessment"""
    assessment = WoundAssessment.query.get_or_404(assessment_id)
    patient = assessment.patient
    
    # Check authorization
    if current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to delete this assessment.', 'error')
        return redirect(url_for('dashboard.index'))
    
    patient_id = assessment.patient_id
    db.session.delete(assessment)
    db.session.commit()
    
    flash('Assessment deleted successfully.', 'success')
    return redirect(url_for('assessments.patient_assessments', patient_id=patient_id))
