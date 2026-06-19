import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, PublicMessage, PublicMessageReply, UserRole

wall_bp = Blueprint('wall', __name__, url_prefix='/wall')

ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webm'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


@wall_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        file    = request.files.get('attachment')
        att_url = att_type = None

        if file and file.filename:
            if not _allowed(file.filename):
                flash('Only image/video files are allowed.', 'error')
                return redirect(url_for('wall.index'))
            fname = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            folder = os.path.join(current_app.root_path,
                                  current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), 'wall')
            os.makedirs(folder, exist_ok=True)
            file.save(os.path.join(folder, fname))
            att_url  = url_for('static', filename=f'uploads/wall/{fname}')
            att_type = file.mimetype

        if not content and not att_url:
            flash('Post cannot be empty.', 'error')
            return redirect(url_for('wall.index'))

        post = PublicMessage(author_id=current_user.id, content=content,
                             attachment_url=att_url, attachment_type=att_type)
        db.session.add(post)
        db.session.commit()
        flash('Post published.', 'success')
        return redirect(url_for('wall.index'))

    posts = PublicMessage.query.order_by(PublicMessage.created_at.desc()).all()
    return render_template('wall/index.html', posts=posts)


@wall_bp.route('/<int:post_id>/reply', methods=['POST'])
@login_required
def reply(post_id):
    post    = PublicMessage.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    if not content:
        flash('Reply cannot be empty.', 'error')
        return redirect(url_for('wall.index'))
    r = PublicMessageReply(post_id=post.id, author_id=current_user.id, content=content)
    db.session.add(r)
    db.session.commit()
    flash('Reply posted.', 'success')
    return redirect(url_for('wall.index'))


@wall_bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = PublicMessage.query.get_or_404(post_id)
    if post.author_id != current_user.id and current_user.role not in [UserRole.ADMIN, UserRole.NURSE]:
        flash('Permission denied.', 'error')
        return redirect(url_for('wall.index'))
    db.session.delete(post)
    db.session.commit()
    flash('Post removed.', 'success')
    return redirect(url_for('wall.index'))
