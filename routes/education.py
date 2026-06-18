import math
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, EducationContent, EducationStatus, EducationBookmark, UserRole
from routes.notifications import push_notification, push_to_all_admins

education_bp = Blueprint('education', __name__, url_prefix='/learn')

CONTENT_TYPES = ['article', 'video', 'infographic', 'guideline', 'quiz']
CATEGORIES = [
    'Wound Care', 'Infection Prevention', 'Nutrition & Recovery',
    'Pain Management', 'Medication', 'Mental Health', 'Newborn Care',
    'Physical Activity', 'Emergency Signs', 'General Health'
]


def _estimate_reading_time(body: str) -> int:
    words = len(body.split())
    return max(1, math.ceil(words / 200))   # average 200 wpm


# ── Public Library ────────────────────────────────────────────────────────────

@education_bp.route('/')
@login_required
def library():
    q          = request.args.get('q', '').strip()
    category   = request.args.get('category', '')
    ctype      = request.args.get('type', '')
    audience   = request.args.get('audience', '')

    query = EducationContent.query.filter_by(
        status=EducationStatus.APPROVED,
        published_to_patients=True
    )

    # HCPs can also see content targeted at them
    if current_user.role.value in ['doctor', 'nurse', 'chw', 'admin']:
        query = EducationContent.query.filter(
            EducationContent.status == EducationStatus.APPROVED
        )

    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(
                EducationContent.title.ilike(like),
                EducationContent.summary.ilike(like),
                EducationContent.body.ilike(like),
                EducationContent.tags.ilike(like),
            )
        )
    if category:
        query = query.filter(EducationContent.category == category)
    if ctype:
        query = query.filter(EducationContent.content_type == ctype)
    if audience:
        query = query.filter(
            db.or_(EducationContent.target_audience == audience,
                   EducationContent.target_audience == 'all')
        )

    featured  = query.filter_by(is_featured=True).order_by(EducationContent.created_at.desc()).limit(3).all()
    articles  = query.order_by(EducationContent.view_count.desc(), EducationContent.created_at.desc()).all()

    # Bookmarked IDs for current user
    bookmarked_ids = {b.content_id for b in EducationBookmark.query.filter_by(user_id=current_user.id).all()}

    # All distinct categories that have published content
    all_categories = [r[0] for r in db.session.query(EducationContent.category).filter(
        EducationContent.status == EducationStatus.APPROVED,
        EducationContent.category != None
    ).distinct().all() if r[0]]

    return render_template('education/library.html',
                           articles=articles, featured=featured,
                           bookmarked_ids=bookmarked_ids,
                           all_categories=sorted(set(all_categories)),
                           content_types=CONTENT_TYPES,
                           q=q, category=category, ctype=ctype, audience=audience)


# ── Article Reader ─────────────────────────────────────────────────────────────

@education_bp.route('/<int:content_id>')
@login_required
def article(content_id):
    ec = EducationContent.query.get_or_404(content_id)

    # Only published content is visible to patients; admins/HCPs see everything
    if not ec.published_to_patients and current_user.role.value in ['patient', 'mother']:
        flash('This content is not available.', 'warning')
        return redirect(url_for('education.library'))

    # Increment view count
    ec.view_count = (ec.view_count or 0) + 1
    db.session.commit()

    is_bookmarked = EducationBookmark.query.filter_by(
        user_id=current_user.id, content_id=content_id).first() is not None

    # Related content: same category, excluding current
    related = EducationContent.query.filter(
        EducationContent.id != content_id,
        EducationContent.category == ec.category,
        EducationContent.status == EducationStatus.APPROVED,
        EducationContent.published_to_patients == True
    ).order_by(EducationContent.view_count.desc()).limit(4).all()

    return render_template('education/article.html',
                           ec=ec, is_bookmarked=is_bookmarked, related=related)


# ── Bookmark Toggle ────────────────────────────────────────────────────────────

@education_bp.route('/<int:content_id>/bookmark', methods=['POST'])
@login_required
def toggle_bookmark(content_id):
    ec = EducationContent.query.get_or_404(content_id)
    bm = EducationBookmark.query.filter_by(
        user_id=current_user.id, content_id=content_id).first()
    if bm:
        db.session.delete(bm)
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'bookmarked': False})
        flash('Removed from bookmarks.', 'info')
    else:
        db.session.add(EducationBookmark(user_id=current_user.id, content_id=content_id))
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'bookmarked': True})
        flash('Saved to bookmarks.', 'success')
    return redirect(url_for('education.article', content_id=content_id))


# ── My Bookmarks ───────────────────────────────────────────────────────────────

@education_bp.route('/bookmarks')
@login_required
def bookmarks():
    bms = (EducationBookmark.query
           .filter_by(user_id=current_user.id)
           .order_by(EducationBookmark.created_at.desc())
           .all())
    return render_template('education/library.html',
                           articles=[b.content for b in bms if b.content],
                           featured=[],
                           bookmarked_ids={b.content_id for b in bms},
                           all_categories=[],
                           content_types=CONTENT_TYPES,
                           q='', category='', ctype='', audience='',
                           page_title='My Bookmarks',
                           is_bookmarks_page=True)


# ── HCP: Submit Content ────────────────────────────────────────────────────────

@education_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if current_user.role.value in ['patient', 'mother']:
        flash('Only healthcare providers can submit content.', 'danger')
        return redirect(url_for('education.library'))

    if request.method == 'POST':
        title    = request.form.get('title', '').strip()
        summary  = request.form.get('summary', '').strip()
        body     = request.form.get('body', '').strip()
        category = request.form.get('category', '').strip() or None
        tags     = request.form.get('tags', '').strip() or None
        ctype    = request.form.get('content_type', 'article')
        video    = request.form.get('video_url', '').strip() or None
        audience = request.form.get('target_audience', 'all')

        if not title or not body:
            flash('Title and body are required.', 'danger')
            return render_template('education/submit.html',
                                   categories=CATEGORIES, content_types=CONTENT_TYPES)

        reading = _estimate_reading_time(body)
        ec = EducationContent(
            title          = title,
            summary        = summary or None,
            body           = body,
            category       = category,
            tags           = tags,
            content_type   = ctype,
            video_url      = video,
            reading_time   = reading,
            target_audience= audience,
            author_id      = current_user.id,
            status         = EducationStatus.PENDING,
        )
        db.session.add(ec)

        # Notify all admins
        push_to_all_admins(
            title   = '📚 New Education Content Submitted',
            message = f'{current_user.get_full_name()} submitted "{title}" for review.',
            notif_type = 'info',
            link    = url_for('admin.education')
        )
        db.session.commit()
        flash('Your content has been submitted for admin review. You will be notified once it is approved.', 'success')
        return redirect(url_for('education.library'))

    return render_template('education/submit.html',
                           categories=CATEGORIES, content_types=CONTENT_TYPES)
