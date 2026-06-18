from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash
from models import (db, User, UserRole, Patient, Message, Alert,
                    AppointmentRequest, AppointmentStatus,
                    EducationContent, EducationStatus,
                    BroadcastMessage, FollowUp, WoundAssessment)
from routes.auth import admin_required
from routes.notifications import push_notification
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    stats = {
        'total_patients': Patient.query.count(),
        'active_patients': Patient.query.filter_by(is_active=True).count(),
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'pending_appointments': AppointmentRequest.query.filter_by(status=AppointmentStatus.PENDING).count(),
        'unresolved_alerts': Alert.query.filter_by(is_resolved=False).count(),
        'pending_education': EducationContent.query.filter_by(status=EducationStatus.PENDING).count(),
        'total_follow_ups': FollowUp.query.count(),
        'completed_follow_ups': FollowUp.query.filter_by(is_completed=True).count(),
    }
    recent_alerts = Alert.query.filter_by(is_resolved=False).order_by(Alert.created_at.desc()).limit(5).all()
    recent_appointments = AppointmentRequest.query.order_by(AppointmentRequest.created_at.desc()).limit(5).all()
    broadcasts = BroadcastMessage.query.order_by(BroadcastMessage.created_at.desc()).limit(5).all()
    hcps = (User.query
            .filter(User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW]))
            .order_by(User.last_name.asc()).all())
    return render_template('admin/dashboard.html', stats=stats,
                           recent_alerts=recent_alerts,
                           recent_appointments=recent_appointments,
                           broadcasts=broadcasts,
                           hcps=hcps)


# ── User Management ───────────────────────────────────────────────────────────

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    role_filter = request.args.get('role', '')
    q = request.args.get('q', '').strip()
    query = User.query
    if role_filter:
        try:
            query = query.filter_by(role=UserRole(role_filter))
        except ValueError:
            pass
    if q:
        query = query.filter(
            (User.first_name.ilike(f'%{q}%')) |
            (User.last_name.ilike(f'%{q}%')) |
            (User.username.ilike(f'%{q}%')) |
            (User.email.ilike(f'%{q}%'))
        )
    users = query.order_by(User.role.asc(), User.last_name.asc()).all()
    return render_template('admin/users.html', users=users, roles=UserRole,
                           role_filter=role_filter, q=q)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.first_name = request.form.get('first_name', user.first_name).strip()
        user.last_name  = request.form.get('last_name',  user.last_name).strip()
        user.email      = request.form.get('email',      user.email).strip()
        user.phone      = request.form.get('phone',      user.phone or '').strip() or None
        user.location   = request.form.get('location',   user.location or '').strip() or None
        role_val = request.form.get('role')
        try:
            user.role = UserRole(role_val)
        except ValueError:
            pass
        db.session.commit()
        flash(f'{user.get_full_name()} updated.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/edit_user.html', user=user, roles=UserRole)


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('admin.users'))
    user.is_active = not user.is_active
    db.session.commit()
    state = 'activated' if user.is_active else 'deactivated'
    flash(f'{user.get_full_name()} has been {state}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_pw = request.form.get('new_password', '').strip()
    if len(new_pw) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('admin.edit_user', user_id=user_id))
    user.password_hash = generate_password_hash(new_pw)
    db.session.commit()
    flash(f'Password for {user.get_full_name()} has been reset.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted.', 'success')
    return redirect(url_for('admin.users'))


# ── Patient Management (admin view) ──────────────────────────────────────────

@admin_bp.route('/patients')
@login_required
@admin_required
def patients():
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    query = Patient.query
    if q:
        query = query.filter(
            (Patient.first_name.ilike(f'%{q}%')) |
            (Patient.last_name.ilike(f'%{q}%')) |
            (Patient.mrn.ilike(f'%{q}%'))
        )
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'discharged':
        query = query.filter_by(is_active=False)
    patients = query.order_by(Patient.last_name.asc()).all()
    hcps = User.query.filter(User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW])).order_by(User.last_name).all()
    return render_template('admin/patients.html', patients=patients, hcps=hcps, q=q, status=status)


@admin_bp.route('/patients/<int:patient_id>/assign-hcp', methods=['POST'])
@login_required
@admin_required
def assign_hcp_to_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    hcp_id = request.form.get('hcp_id', type=int)
    if hcp_id:
        patient.primary_doctor_id = hcp_id
        db.session.commit()
        flash('HCP assigned successfully.', 'success')
    return redirect(url_for('admin.patients'))


# ── Chat Monitoring ───────────────────────────────────────────────────────────

@admin_bp.route('/chats')
@login_required
@admin_required
def chat_monitor():
    """List all patients that have chat activity."""
    patients_with_chats = (Patient.query
                           .join(Message, Message.patient_id == Patient.id)
                           .group_by(Patient.id)
                           .order_by(func.max(Message.created_at).desc())
                           .all())
    return render_template('admin/chat_monitor.html', patients=patients_with_chats)


@admin_bp.route('/chats/patient/<int:patient_id>')
@login_required
@admin_required
def view_patient_chat(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    messages = Message.query.filter_by(patient_id=patient_id).order_by(Message.created_at.asc()).all()
    return render_template('admin/view_chat.html', patient=patient, messages=messages)


@admin_bp.route('/broadcast', methods=['GET', 'POST'])
@login_required
@admin_required
def broadcast():
    if request.method == 'POST':
        content    = request.form.get('content', '').strip()
        target     = request.form.get('target', 'all')
        target_uid = request.form.get('target_user_id', type=int)
        if not content:
            flash('Message cannot be empty.', 'error')
            return redirect(url_for('admin.broadcast'))
        msg = BroadcastMessage(
            sender_id=current_user.id,
            content=content,
            target=target,
            target_user_id=target_uid or None
        )
        db.session.add(msg)
        db.session.commit()
        flash('Broadcast sent.', 'success')
        return redirect(url_for('admin.broadcast'))
    broadcasts = BroadcastMessage.query.order_by(BroadcastMessage.created_at.desc()).all()
    users_for_dm = User.query.filter(User.id != current_user.id).order_by(User.last_name).all()
    return render_template('admin/broadcast.html', broadcasts=broadcasts, users=users_for_dm)


# ── Appointment Management ────────────────────────────────────────────────────

@admin_bp.route('/appointments')
@login_required
@admin_required
def appointments():
    status_filter = request.args.get('status', '')
    query = AppointmentRequest.query
    if status_filter:
        try:
            query = query.filter_by(status=AppointmentStatus(status_filter))
        except ValueError:
            pass
    appts = query.order_by(AppointmentRequest.created_at.desc()).all()
    hcps  = User.query.filter(User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW])).order_by(User.last_name).all()
    return render_template('admin/appointments.html', appointments=appts,
                           hcps=hcps, statuses=AppointmentStatus,
                           status_filter=status_filter)


@admin_bp.route('/appointments/<int:appt_id>/action', methods=['POST'])
@login_required
@admin_required
def appointment_action(appt_id):
    appt   = AppointmentRequest.query.get_or_404(appt_id)
    action = request.form.get('action')
    notes  = request.form.get('admin_notes', '').strip()
    hcp_id = request.form.get('hcp_id', type=int)
    reschedule_date_str = request.form.get('scheduled_date', '').strip()

    if action == 'approve':
        appt.status = AppointmentStatus.APPROVED
    elif action == 'reject':
        appt.status = AppointmentStatus.REJECTED
    elif action == 'reschedule':
        appt.status = AppointmentStatus.RESCHEDULED
        if reschedule_date_str:
            try:
                appt.scheduled_date = datetime.strptime(reschedule_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
    if hcp_id:
        appt.assigned_hcp_id = hcp_id
    appt.admin_notes = notes
    appt.updated_at  = datetime.utcnow()

    # Notify the patient's linked user account
    patient = appt.patient
    if patient and patient.user_id:
        if action == 'approve':
            date_str = appt.scheduled_date.strftime('%B %d, %Y at %H:%M') if appt.scheduled_date else appt.preferred_date.strftime('%B %d, %Y at %H:%M')
            title   = '✅ Appointment Approved'
            message = f'Your appointment request has been approved for {date_str}.'
            if hcp_id:
                hcp = User.query.get(hcp_id)
                if hcp:
                    message += f' Your provider: {hcp.get_full_name()}.'
            if notes:
                message += f' Note: {notes}'
            notif_type = 'appointment'
        elif action == 'reject':
            title   = '❌ Appointment Rejected'
            message = 'Your appointment request has been rejected.'
            if notes:
                message += f' Reason: {notes}'
            notif_type = 'reminder'
        else:  # reschedule
            date_str = appt.scheduled_date.strftime('%B %d, %Y at %H:%M') if appt.scheduled_date else '(date TBD)'
            title   = '🔄 Appointment Rescheduled'
            message = f'Your appointment has been rescheduled to {date_str}.'
            if notes:
                message += f' Note: {notes}'
            notif_type = 'appointment'
        push_notification(
            user_id=patient.user_id,
            title=title,
            message=message,
            notif_type=notif_type,
            link=url_for('appointments.my_appointments')
        )

    # Also notify assigned HCP
    if hcp_id and action in ('approve', 'reschedule'):
        date_str = (appt.scheduled_date or appt.preferred_date).strftime('%B %d, %Y at %H:%M')
        push_notification(
            user_id=hcp_id,
            title='📅 New Appointment Assigned',
            message=f'You have been assigned to {patient.get_full_name()}\'s appointment on {date_str}.',
            notif_type='appointment',
            link=url_for('appointments.list_all')
        )

    db.session.commit()
    flash(f'Appointment {action}d.', 'success')
    return redirect(url_for('admin.appointments'))


@admin_bp.route('/appointments/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_appointment():
    patients = Patient.query.order_by(Patient.last_name).all()
    hcps     = User.query.filter(User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW])).order_by(User.last_name).all()

    if request.method == 'POST':
        patient_id       = request.form.get('patient_id', type=int)
        preferred_date   = request.form.get('preferred_date', '').strip()
        scheduled_date   = request.form.get('scheduled_date', '').strip()
        reason           = request.form.get('reason', '').strip()
        hcp_id           = request.form.get('hcp_id', type=int)
        admin_notes      = request.form.get('admin_notes', '').strip()
        status_val       = request.form.get('status', 'approved')

        if not patient_id or not preferred_date:
            flash('Patient and preferred date are required.', 'danger')
            return render_template('admin/create_appointment.html', patients=patients, hcps=hcps, statuses=AppointmentStatus)

        try:
            pref_dt  = datetime.strptime(preferred_date, '%Y-%m-%dT%H:%M')
            sched_dt = datetime.strptime(scheduled_date, '%Y-%m-%dT%H:%M') if scheduled_date else None
        except ValueError:
            flash('Invalid date format.', 'danger')
            return render_template('admin/create_appointment.html', patients=patients, hcps=hcps, statuses=AppointmentStatus)

        try:
            status_enum = AppointmentStatus(status_val)
        except ValueError:
            status_enum = AppointmentStatus.APPROVED

        appt = AppointmentRequest(
            patient_id      = patient_id,
            requested_by_id = current_user.id,
            preferred_date  = pref_dt,
            scheduled_date  = sched_dt,
            reason          = reason,
            status          = status_enum,
            assigned_hcp_id = hcp_id or None,
            admin_notes     = admin_notes,
        )
        db.session.add(appt)

        # Notify patient
        patient = Patient.query.get(patient_id)
        if patient and patient.user_id:
            date_label = (sched_dt or pref_dt).strftime('%B %d, %Y at %H:%M')
            msg = f'An appointment has been scheduled for you on {date_label}.'
            if hcp_id:
                hcp = User.query.get(hcp_id)
                if hcp:
                    msg += f' Provider: {hcp.get_full_name()}.'
            if admin_notes:
                msg += f' Note: {admin_notes}'
            push_notification(patient.user_id, '📅 Appointment Scheduled', msg,
                              notif_type='appointment',
                              link=url_for('appointments.my_appointments'))

        # Notify assigned HCP
        if hcp_id and patient:
            date_label = (sched_dt or pref_dt).strftime('%B %d, %Y at %H:%M')
            push_notification(hcp_id, '📅 New Appointment Assigned',
                              f'You are assigned to {patient.get_full_name()}\'s appointment on {date_label}.',
                              notif_type='appointment',
                              link=url_for('appointments.list_all'))

        db.session.commit()
        flash('Appointment created successfully.', 'success')
        return redirect(url_for('admin.appointments'))

    return render_template('admin/create_appointment.html', patients=patients, hcps=hcps, statuses=AppointmentStatus)


@admin_bp.route('/alerts/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_alert():
    patients = Patient.query.order_by(Patient.last_name).all()
    hcps     = User.query.filter(User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW])).order_by(User.last_name).all()

    if request.method == 'POST':
        patient_id = request.form.get('patient_id', type=int)
        alert_type = request.form.get('alert_type', '').strip()
        severity   = request.form.get('severity', 'medium').strip()
        message    = request.form.get('message', '').strip()
        hcp_id     = request.form.get('hcp_id', type=int)

        if not patient_id or not alert_type or not message:
            flash('Patient, alert type, and message are required.', 'danger')
            return render_template('admin/create_alert.html', patients=patients, hcps=hcps)

        alert = Alert(
            patient_id      = patient_id,
            alert_type      = alert_type,
            severity        = severity,
            message         = message,
            assigned_hcp_id = hcp_id or None,
        )
        db.session.add(alert)

        patient = Patient.query.get(patient_id)
        # Notify patient's user account
        if patient and patient.user_id:
            push_notification(patient.user_id,
                              f'⚠️ {severity.capitalize()} Alert: {alert_type}',
                              message[:200],
                              notif_type='alert',
                              link=url_for('dashboard.index'))

        # Notify assigned HCP
        if hcp_id and patient:
            push_notification(hcp_id,
                              f'⚠️ Alert Assigned — {severity.capitalize()}',
                              f'{patient.get_full_name()}: {alert_type}. {message[:120]}',
                              notif_type='alert',
                              link=url_for('patients.view_patient', patient_id=patient_id))

        db.session.commit()
        flash('Alert created and notifications sent.', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/create_alert.html', patients=patients, hcps=hcps)


@admin_bp.route('/notifications/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_notification():
    users = User.query.filter_by(is_active=True).order_by(User.last_name).all()

    if request.method == 'POST':
        target      = request.form.get('target', 'user')   # user | all_patients | all_hcps | all
        user_id     = request.form.get('user_id', type=int)
        title       = request.form.get('title', '').strip()
        message     = request.form.get('message', '').strip()
        notif_type  = request.form.get('notif_type', 'info')
        link        = request.form.get('link', '').strip() or None

        if not title or not message:
            flash('Title and message are required.', 'danger')
            return render_template('admin/create_notification.html', users=users)

        recipients = []
        if target == 'user' and user_id:
            u = User.query.get(user_id)
            if u:
                recipients = [u]
        elif target == 'all_patients':
            recipients = User.query.filter_by(is_active=True).filter(
                User.role.in_([UserRole.PATIENT, UserRole.MOTHER])).all()
        elif target == 'all_hcps':
            recipients = User.query.filter_by(is_active=True).filter(
                User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW])).all()
        elif target == 'all':
            recipients = User.query.filter_by(is_active=True).all()

        if not recipients:
            flash('No recipients found for the selected target.', 'warning')
            return render_template('admin/create_notification.html', users=users)

        for u in recipients:
            push_notification(u.id, title, message, notif_type=notif_type, link=link or None)

        db.session.commit()
        flash(f'Notification sent to {len(recipients)} recipient(s).', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin/create_notification.html', users=users)


@admin_bp.route('/alerts/<int:alert_id>/assign-hcp', methods=['POST'])
@login_required
@admin_required
def assign_alert_hcp(alert_id):
    alert  = Alert.query.get_or_404(alert_id)
    hcp_id = request.form.get('hcp_id', type=int)
    if hcp_id:
        alert.assigned_hcp_id = hcp_id
        # Notify assigned HCP
        push_notification(
            user_id=hcp_id,
            title='⚠️ Alert Assigned to You',
            message=f'You have been assigned to a {alert.severity} alert for patient '
                    f'{alert.patient.get_full_name()}: {alert.alert_type}. {alert.message[:100]}',
            notif_type='alert',
            link=url_for('patients.view_patient', patient_id=alert.patient_id)
        )
        db.session.commit()
        flash('HCP assigned to alert.', 'success')
    return redirect(request.referrer or url_for('admin.dashboard'))


# ── Education Content Management ──────────────────────────────────────────────

@admin_bp.route('/education')
@login_required
@admin_required
def education():
    status_filter = request.args.get('status', '')
    query = EducationContent.query
    if status_filter:
        try:
            query = query.filter_by(status=EducationStatus(status_filter))
        except ValueError:
            pass
    contents = query.order_by(EducationContent.created_at.desc()).all()
    return render_template('admin/education.html', contents=contents,
                           statuses=EducationStatus, status_filter=status_filter)


@admin_bp.route('/education/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_education():
    if request.method == 'POST':
        ec = EducationContent(
            title=request.form.get('title', '').strip(),
            body=request.form.get('body', '').strip(),
            category=request.form.get('category', '').strip() or None,
            author_id=current_user.id,
            status=EducationStatus.APPROVED,
            approved_by_id=current_user.id,
            published_to_patients=request.form.get('publish') == 'on'
        )
        db.session.add(ec)
        db.session.commit()
        flash('Education content created.', 'success')
        return redirect(url_for('admin.education'))
    return render_template('admin/education_form.html', content=None)


@admin_bp.route('/education/<int:content_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_education(content_id):
    ec = EducationContent.query.get_or_404(content_id)
    if request.method == 'POST':
        ec.title    = request.form.get('title', ec.title).strip()
        ec.body     = request.form.get('body',  ec.body).strip()
        ec.category = request.form.get('category', ec.category or '').strip() or None
        ec.published_to_patients = request.form.get('publish') == 'on'
        ec.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Content updated.', 'success')
        return redirect(url_for('admin.education'))
    return render_template('admin/education_form.html', content=ec)


@admin_bp.route('/education/<int:content_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_education(content_id):
    ec = EducationContent.query.get_or_404(content_id)
    ec.status = EducationStatus.APPROVED
    ec.approved_by_id = current_user.id
    db.session.commit()
    flash('Content approved.', 'success')
    return redirect(url_for('admin.education'))


@admin_bp.route('/education/<int:content_id>/publish', methods=['POST'])
@login_required
@admin_required
def publish_education(content_id):
    ec = EducationContent.query.get_or_404(content_id)
    ec.published_to_patients = not ec.published_to_patients
    db.session.commit()
    state = 'published to' if ec.published_to_patients else 'unpublished from'
    flash(f'Content {state} patient dashboard.', 'success')
    return redirect(url_for('admin.education'))


@admin_bp.route('/education/<int:content_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_education(content_id):
    ec = EducationContent.query.get_or_404(content_id)
    db.session.delete(ec)
    db.session.commit()
    flash('Content deleted.', 'success')
    return redirect(url_for('admin.education'))


# ── Reports & Analytics ───────────────────────────────────────────────────────

@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    # Infection rate
    total_assessments  = WoundAssessment.query.count()
    infected_count     = WoundAssessment.query.filter_by(status='infected').count()
    infection_rate     = round(infected_count / total_assessments * 100, 1) if total_assessments else 0

    # Follow-up stats
    total_fu     = FollowUp.query.count()
    completed_fu = FollowUp.query.filter_by(is_completed=True).count()
    missed_fu    = total_fu - completed_fu

    # Wound status distribution
    from models import WoundStatus
    wound_stats = {}
    for ws in WoundStatus:
        wound_stats[ws.value] = WoundAssessment.query.filter(
            WoundAssessment.status == ws).count()

    # User activity: messages sent per role
    from sqlalchemy import func as sqlfunc
    msg_by_role = (db.session.query(Message.sender_role, sqlfunc.count(Message.id))
                   .group_by(Message.sender_role).all())

    # Patient registrations per month (last 6 months)
    from models import Patient as PatModel
    from datetime import timedelta
    now = datetime.utcnow()
    monthly = []
    for i in range(5, -1, -1):
        start = (now.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        end   = (start.replace(month=start.month % 12 + 1, day=1)
                 if start.month < 12
                 else start.replace(year=start.year + 1, month=1, day=1))
        count = PatModel.query.filter(PatModel.created_at >= start, PatModel.created_at < end).count()
        monthly.append({'month': start.strftime('%b %Y'), 'count': count})

    # System usage by patients and HCPs
    patient_msgs = sum(c for r, c in msg_by_role if r in ('patient', 'mother'))
    hcp_msgs     = sum(c for r, c in msg_by_role if r not in ('patient', 'mother'))

    return render_template('admin/reports.html',
                           total_assessments=total_assessments,
                           infected_count=infected_count,
                           infection_rate=infection_rate,
                           total_fu=total_fu,
                           completed_fu=completed_fu,
                           missed_fu=missed_fu,
                           wound_stats=wound_stats,
                           msg_by_role=dict(msg_by_role),
                           monthly=monthly,
                           patient_msgs=patient_msgs,
                           hcp_msgs=hcp_msgs)
