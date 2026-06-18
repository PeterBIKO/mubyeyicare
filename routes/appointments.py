from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_
from models import db, Patient, AppointmentRequest, AppointmentStatus, UserRole, User
from routes.notifications import push_notification, push_to_all_admins
from datetime import datetime

appointments_bp = Blueprint('appointments', __name__, url_prefix='/appointments')


@appointments_bp.route('/request', methods=['GET', 'POST'])
@login_required
def request_appointment():
    """Patient submits a new appointment request."""
    if current_user.role not in [UserRole.PATIENT, UserRole.MOTHER]:
        flash('Only patients can request appointments.', 'error')
        return redirect(url_for('dashboard.index'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if not patient:
        patient = Patient.query.filter(
            or_(Patient.email == current_user.email,
                Patient.phone == current_user.phone)
        ).first()

    if not patient:
        flash('No patient profile linked to your account.', 'error')
        return redirect(url_for('auth.profile'))

    if request.method == 'POST':
        date_str = request.form.get('preferred_date', '').strip()
        time_str = request.form.get('preferred_time', '09:00').strip()
        reason   = request.form.get('reason', '').strip()

        if not date_str:
            flash('Please provide a preferred date.', 'error')
            return redirect(url_for('appointments.request_appointment'))

        try:
            preferred_dt = datetime.strptime(f'{date_str} {time_str}', '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Invalid date/time format.', 'error')
            return redirect(url_for('appointments.request_appointment'))

        appt = AppointmentRequest(
            patient_id=patient.id,
            requested_by_id=current_user.id,
            preferred_date=preferred_dt,
            reason=reason,
            status=AppointmentStatus.PENDING
        )
        db.session.add(appt)

        # Notify all admins of the new request
        push_to_all_admins(
            title='New Appointment Request',
            message=f'{patient.get_full_name()} has requested an appointment on '
                    f'{preferred_dt.strftime("%b %d, %Y at %H:%M")}.'
                    + (f' Reason: {reason[:80]}' if reason else ''),
            notif_type='appointment',
            link=url_for('admin.appointments')
        )
        db.session.commit()
        flash('Appointment request submitted. You will be notified once it is reviewed.', 'success')
        return redirect(url_for('appointments.my_appointments'))

    return render_template('appointments/request.html', patient=patient)


@appointments_bp.route('/my')
@login_required
def my_appointments():
    """Patient views their own appointment requests."""
    if current_user.role not in [UserRole.PATIENT, UserRole.MOTHER]:
        return redirect(url_for('appointments.list_all'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if not patient:
        patient = Patient.query.filter(
            or_(Patient.email == current_user.email,
                Patient.phone == current_user.phone)
        ).first()

    if not patient:
        flash('No patient profile linked to your account.', 'error')
        return redirect(url_for('auth.profile'))

    appts = (AppointmentRequest.query
             .filter_by(patient_id=patient.id)
             .order_by(AppointmentRequest.created_at.desc())
             .all())
    return render_template('appointments/my.html', appointments=appts,
                           statuses=AppointmentStatus, patient=patient)


@appointments_bp.route('/')
@login_required
def list_all():
    """HCP / Admin views all appointment requests."""
    if current_user.role in [UserRole.PATIENT, UserRole.MOTHER]:
        return redirect(url_for('appointments.my_appointments'))

    status_filter = request.args.get('status', '')
    query = AppointmentRequest.query
    if status_filter:
        try:
            query = query.filter_by(status=AppointmentStatus(status_filter))
        except ValueError:
            pass
    if current_user.role not in [UserRole.ADMIN]:
        # HCPs see appointments for their patients
        from models import Patient as Pat
        patient_ids = [p.id for p in Pat.query.filter_by(primary_doctor_id=current_user.id).all()]
        query = query.filter(AppointmentRequest.patient_id.in_(patient_ids))

    appts = query.order_by(AppointmentRequest.created_at.desc()).all()
    hcps  = User.query.filter(User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW])).order_by(User.last_name).all()
    return render_template('appointments/list.html', appointments=appts,
                           hcps=hcps, statuses=AppointmentStatus,
                           status_filter=status_filter)
