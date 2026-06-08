import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from models import db, Patient, Message, User, UserRole
from routes.auth import doctor_nurse_required

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi', 'webm'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@chat_bp.route('/')
@login_required
@doctor_nurse_required
def chat_list():
    """List patients available for chat"""
    if current_user.role == UserRole.ADMIN:
        patients = Patient.query.order_by(Patient.last_name.asc(), Patient.first_name.asc()).all()
    elif current_user.role == UserRole.CHW:
        patients = Patient.query.order_by(Patient.last_name.asc(), Patient.first_name.asc()).all()
    else:
        patients = Patient.query.filter_by(primary_doctor_id=current_user.id).order_by(Patient.last_name.asc(), Patient.first_name.asc()).all()

    return render_template('chat/list.html', patients=patients)

@chat_bp.route('/me')
@login_required
def patient_self_chat():
    if current_user.role not in [UserRole.PATIENT, UserRole.MOTHER]:
        return redirect(url_for('chat.chat_list'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if not patient:
        patient = Patient.query.filter(
            or_(Patient.email == current_user.email, Patient.phone == current_user.phone)
        ).first()

    if not patient:
        flash('No patient profile linked to this account.', 'error')
        return redirect(url_for('dashboard.index'))

    providers = User.query.filter(User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW])).order_by(User.role.asc(), User.last_name.asc(), User.first_name.asc()).all()
    return render_template('chat/provider_list.html', patient=patient, providers=providers)


@chat_bp.route('/patient/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def patient_chat(patient_id):
    """Chat with a specific patient"""
    patient = Patient.query.get_or_404(patient_id)
    if current_user.role in [UserRole.PATIENT, UserRole.MOTHER]:
        if patient.user_id != current_user.id and (patient.email != current_user.email and patient.phone != current_user.phone):
            flash('You do not have permission to view this chat.', 'error')
            return redirect(url_for('dashboard.index'))
    elif current_user.role == UserRole.CHW:
        pass
    elif current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        flash('You do not have permission to chat with this patient.', 'error')
        return redirect(url_for('dashboard.index'))

    provider = None
    provider_id = request.args.get('provider_id', type=int)
    if request.method == 'POST' and not provider_id:
        provider_id = request.form.get('provider_id', type=int)
    if provider_id:
        provider = User.query.filter(User.id == provider_id, User.role.in_([UserRole.DOCTOR, UserRole.NURSE, UserRole.CHW])).first()

    if request.method == 'POST':
        content = request.form.get('message', '').strip()
        file = request.files.get('attachment')
        attachment_filename = None
        attachment_type = None
        attachment_url = None

        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Only image and video files are allowed.', 'error')
                return redirect(url_for('chat.patient_chat', patient_id=patient.id, provider_id=provider.id if provider else None))

            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            upload_folder = os.path.join(current_app.root_path, current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'chat')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, unique_name)
            file.save(file_path)

            attachment_filename = filename
            attachment_type = file.mimetype
            attachment_url = url_for('static', filename=f'uploads/chat/{unique_name}')

        if not content and not attachment_url:
            flash('Please enter a message or attach an image/video.', 'error')
            return redirect(url_for('chat.patient_chat', patient_id=patient.id, provider_id=provider.id if provider else None))

        message = Message(
            patient_id=patient.id,
            sender_id=current_user.id,
            sender_role=current_user.role.value,
            content=content,
            attachment_filename=attachment_filename,
            attachment_type=attachment_type,
            attachment_url=attachment_url
        )
        db.session.add(message)
        db.session.commit()

        flash('Message sent.', 'success')
        if provider:
            return redirect(url_for('chat.patient_chat', patient_id=patient.id, provider_id=provider.id))
        return redirect(url_for('chat.patient_chat', patient_id=patient.id))

    messages = Message.query.filter_by(patient_id=patient.id).order_by(Message.created_at.asc()).all()
    return render_template('chat/patient_chat.html', patient=patient, messages=messages, selected_provider=provider)


@chat_bp.route('/patient/<int:patient_id>/messages')
@login_required
def get_messages(patient_id):
    """Return messages as JSON; optional ?since_id=NN to get newer messages"""
    patient = Patient.query.get_or_404(patient_id)
    # permission checks similar to patient_chat
    if current_user.role in [UserRole.PATIENT, UserRole.MOTHER]:
        if patient.user_id != current_user.id and (patient.email != current_user.email and patient.phone != current_user.phone):
            return jsonify({'error': 'forbidden'}), 403
    elif current_user.role == UserRole.CHW:
        pass
    elif current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403

    since_id = request.args.get('since_id', type=int)
    query = Message.query.filter_by(patient_id=patient_id)
    if since_id:
        query = query.filter(Message.id > since_id)
    msgs = query.order_by(Message.created_at.asc()).all()

    result = []
    for m in msgs:
        result.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'sender_name': m.sender.get_full_name() if m.sender else m.sender_role,
            'sender_role': m.sender_role,
            'content': m.content,
            'attachment_url': m.attachment_url,
            'attachment_type': m.attachment_type,
            'attachment_filename': m.attachment_filename,
            'created_at': m.created_at.isoformat()
        })
    return jsonify(result)


@chat_bp.route('/patient/<int:patient_id>/send', methods=['POST'])
@login_required
def send_message_ajax(patient_id):
    """AJAX endpoint to send a message (supports file uploads via FormData)"""
    patient = Patient.query.get_or_404(patient_id)
    # permission checks
    if current_user.role in [UserRole.PATIENT, UserRole.MOTHER]:
        if patient.user_id != current_user.id and (patient.email != current_user.email and patient.phone != current_user.phone):
            return jsonify({'error': 'forbidden'}), 403
    elif current_user.role == UserRole.CHW:
        pass
    elif current_user.role not in [UserRole.ADMIN] and patient.primary_doctor_id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403

    content = request.form.get('message', '').strip()
    file = request.files.get('attachment')
    attachment_filename = None
    attachment_type = None
    attachment_url = None

    if file and file.filename:
        if not allowed_file(file.filename):
            return jsonify({'error': 'invalid_file'}), 400
        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        upload_folder = os.path.join(current_app.root_path, current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'chat')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, unique_name)
        file.save(file_path)

        attachment_filename = filename
        attachment_type = file.mimetype
        attachment_url = url_for('static', filename=f'uploads/chat/{unique_name}')

    if not content and not attachment_url:
        return jsonify({'error': 'empty'}), 400

    message = Message(
        patient_id=patient.id,
        sender_id=current_user.id,
        sender_role=current_user.role.value,
        content=content,
        attachment_filename=attachment_filename,
        attachment_type=attachment_type,
        attachment_url=attachment_url
    )
    db.session.add(message)
    db.session.commit()

    return jsonify({
        'id': message.id,
        'sender_id': message.sender_id,
        'sender_name': message.sender.get_full_name() if message.sender else message.sender_role,
        'sender_role': message.sender_role,
        'content': message.content,
        'attachment_url': message.attachment_url,
        'attachment_type': message.attachment_type,
        'attachment_filename': message.attachment_filename,
        'created_at': message.created_at.isoformat()
    }), 201

