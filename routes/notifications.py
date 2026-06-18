from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from models import db, Notification, UserRole, User

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')


# ── Helper — call this from any other route ───────────────────────────────────

def push_notification(user_id, title, message, notif_type='info', link=None):
    """Create an in-app notification for a specific user."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notif_type=notif_type,
        link=link
    )
    db.session.add(notif)
    # Caller is responsible for db.session.commit()


def push_to_all_admins(title, message, notif_type='info', link=None):
    """Send the same notification to every admin user."""
    admins = User.query.filter_by(role=UserRole.ADMIN, is_active=True).all()
    for admin in admins:
        push_notification(admin.id, title, message, notif_type, link)


# ── Routes ────────────────────────────────────────────────────────────────────

@notifications_bp.route('/')
@login_required
def index():
    notifs = (Notification.query
              .filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc())
              .all())
    return render_template('notifications/index.html', notifications=notifs)


@notifications_bp.route('/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_read(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    # If AJAX return JSON, otherwise redirect back
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})
    next_url = request.args.get('next') or (n.link if n.link else url_for('notifications.index'))
    return redirect(next_url)


@notifications_bp.route('/read-all', methods=['POST'])
@login_required
def mark_all_read():
    (Notification.query
     .filter_by(user_id=current_user.id, is_read=False)
     .update({'is_read': True}))
    db.session.commit()
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/<int:notif_id>/delete', methods=['POST'])
@login_required
def delete(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    db.session.delete(n)
    db.session.commit()
    return redirect(url_for('notifications.index'))
