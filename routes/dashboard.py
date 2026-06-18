from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from models import db, User, Patient, FollowUp, WoundAssessment, Alert, UserRole, VitalSigns, AppointmentRequest, AppointmentStatus, EducationContent, EducationStatus
from datetime import datetime, timedelta, timezone

health_education_topics = [
    {
        'title': 'Post-Cesarean Wound Care Basics',
        'title_rw': 'Inyigisho z\'ibanze zo kwita ku gisebe cya cesarean',
        'description': 'Learn how to keep your incision clean, recognize infection signs, and support healthy healing.',
        'description_rw': 'Menya uko usukura neza ahakirijwe, uko wamenya ibimenyetso by\'ubwandu, kandi ukomeze gukira neza.',
        'details': 'Keep the incision area clean and dry, change dressings as directed, and avoid submerging the wound in water until your provider clears it. Monitor for redness, swelling, warmth, or unusual discharge, and contact your care team if any of these occur. Gentle movement and proper hygiene are key to preventing infection and promoting recovery.',
        'details_rw': 'Gira isuku ahakirijwe kandi wirinde kumanza amazi kugeza umujyanama wawe abyemeye. Hindura ibikotaniro nk\'uko wabiduhuje, kandi menya ibimenyetso nko gutukura, kubyimba, kumanuka umuriro cyangwa amacandwe atari meza. Ukoreshe imyitozo yoroheje kandi isuku ni ingenzi mu gukumira ubwandu no kwihutisha gukira.'
    },
    {
        'title': 'Pain Management After Surgery',
        'title_rw': 'Gucunga ububabare nyuma yo kubagwa',
        'description': 'Guidance on pain medicines, rest, and safe movement after your c-section.',
        'description_rw': 'Inama ku miti y\'ububabare, kuruhuka, no kugenda ufite umutekano nyuma ya cesarean.',
        'details': 'Take prescribed pain medications exactly as instructed and use non-drug methods such as ice packs, deep breathing, and rest when possible. Avoid heavy lifting and sudden movements while your body heals. Talk to your care provider about any pain that is worsening, does not improve, or is accompanied by fever.',
        'details_rw': 'Fata imiti yagenwe neza uko igomba gufatwa, ukoreshe uburyo budashora umubiri nk\'udupaki dukonje, guhumeka neza, no kuruhuka igihe gikwiriye. Irinde guterura ibintu biremereye no kwimuka bitunguranye igihe umubiri wawe ukiri mu gukira. Ganira n\'umuganga wawe niba ububabare bukomeza gukaza cyangwa ubone ikibazo gikomeye.'
    },
    {
        'title': 'Nutrition for Recovery',
        'title_rw': 'Imirire yo gukira',
        'description': 'Diet tips to support wound healing, energy, and breastfeeding needs.',
        'description_rw': 'Inama z\'imirire zishyigikira gukira kw\'ibisebe, ingufu, no guhabwa amata.',
        'details': 'Focus on a balanced diet rich in protein, fiber, healthy fats, and fluids to support tissue repair and energy levels. Include fruits, vegetables, lean meats, eggs, beans, and whole grains, and drink plenty of water throughout the day. Small, frequent meals can help manage fatigue and support breastfeeding if you are nursing.',
        'details_rw': 'Hitamo indyo yuzuye irimo proteyine, fibre, amavuta meza, n\'amazi menshi kugira ngo wunganire gusana uturemangingo no kugira ingufu. Shyiramo imbuto, imboga, inyama zidafite amavuta menshi, amagi, ibishyimbo, n\'ibinyampeke byuzuye, kandi unywe amazi menshi buri munsi. Fata ibiryo bicye kenshi gishoboka kugira ngo wirinde kunanirwa no gufasha guhabwa amata niba ubyinshije.'
    },
    {
        'title': 'When to Contact Your Care Team',
        'title_rw': 'Igihe cyo kuvugana n\'itsinda ryita ku buzima',
        'description': 'Red flags and symptoms that need prompt attention from your provider.',
        'description_rw': 'Ibimenyetso by\'ibanga n\'ibyo ugomba gutangariza umuganga wawe bidatinze.',
        'details': 'Reach out immediately if you experience heavy bleeding, fever over 38°C, severe abdominal pain, foul-smelling discharge, or difficulty breathing. Also report any new numbness, swelling, or changes in incision appearance. Early communication helps your care team respond quickly and prevent complications.',
        'details_rw': 'Hamagarira vuba niba ubona amaraso menshi, umuriro urenze 38°C, ububabare bukabije mu nda, ibisohoka bifite umwanda, cyangwa ikibazo cyo guhumeka. Menyesha kandi niba wumva gukorora k\'umubiri gashya, kubyimba, cyangwa impinduka ku gisebe. Kuvugana hakiri kare bifasha itsinda ryawe kugufasha vuba no kwirinda ingorane.'
    }
]

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard"""
    if current_user.role in [UserRole.PATIENT, UserRole.MOTHER]:
        return redirect(url_for('dashboard.patient_dashboard'))
    else:
        return redirect(url_for('dashboard.provider_dashboard'))

@dashboard_bp.route('/provider')
@login_required
def provider_dashboard():
    """Dashboard for healthcare providers (doctor/nurse)"""
    if current_user.role in [UserRole.PATIENT, UserRole.MOTHER]:
        return redirect(url_for('dashboard.patient_dashboard'))
    
    # Get statistics
    if current_user.role == UserRole.ADMIN:
        total_patients = Patient.query.count()
        discharged_patients = Patient.query.filter_by(is_active=False).count()
        active_follow_ups = FollowUp.query.filter_by(is_completed=False).count()
        total_users = User.query.count()
    elif current_user.role == UserRole.CHW:
        # CHW sees only patients in their location
        if current_user.location:
            loc_q = Patient.query.filter_by(location=current_user.location)
            total_patients = loc_q.count()
            discharged_patients = loc_q.filter_by(is_active=False).count()
            patient_ids = [p.id for p in loc_q.all()]
            active_follow_ups = FollowUp.query.filter(
                FollowUp.patient_id.in_(patient_ids),
                FollowUp.is_completed == False
            ).count()
        else:
            total_patients = 0
            discharged_patients = 0
            active_follow_ups = 0
        total_users = User.query.count()
    else:
        # Doctor/Nurse sees only their patients
        total_patients = current_user.patients.count()
        discharged_patients = current_user.patients.filter_by(is_active=False).count()
        active_follow_ups = FollowUp.query.filter_by(created_by_id=current_user.id, is_completed=False).count()
        total_users = User.query.count()
    
    # Get alerts
    alerts = Alert.query.filter_by(is_resolved=False).order_by(Alert.created_at.desc()).limit(10).all()
    
    # Get recent follow-ups
    if current_user.role == UserRole.ADMIN:
        recent_follow_ups = FollowUp.query.order_by(FollowUp.follow_up_date.desc()).limit(5).all()
    else:
        recent_follow_ups = FollowUp.query.filter_by(created_by_id=current_user.id).order_by(FollowUp.follow_up_date.desc()).limit(5).all()
    
    return render_template('dashboard/provider_dashboard.html',
                         total_patients=total_patients,
                         discharged_patients=discharged_patients,
                         active_follow_ups=active_follow_ups,
                         total_users=total_users,
                         alerts=alerts,
                         recent_follow_ups=recent_follow_ups)

@dashboard_bp.route('/patient')
@login_required
def patient_dashboard():
    """Dashboard for patients"""
    if current_user.role not in [UserRole.PATIENT, UserRole.MOTHER]:
        return redirect(url_for('dashboard.provider_dashboard'))

    patient = Patient.query.filter_by(user_id=current_user.id).first()
    if not patient:
        patient = Patient.query.filter(
            or_(Patient.email == current_user.email, Patient.phone == current_user.phone)
        ).first()

    if not patient:
        flash('No patient profile is linked to your account. Please link a patient record from your profile.', 'error')
        return redirect(url_for('auth.profile'))

    recent_vitals = (VitalSigns.query
                     .join(FollowUp)
                     .filter(FollowUp.patient_id == patient.id)
                     .order_by(VitalSigns.recorded_date.desc())
                     .limit(3).all())

    alerts = (Alert.query
              .filter_by(patient_id=patient.id, is_resolved=False)
              .order_by(Alert.created_at.desc())
              .limit(10).all())

    recent_assessments = (WoundAssessment.query
                          .filter_by(patient_id=patient.id)
                          .order_by(WoundAssessment.assessment_date.desc())
                          .limit(5).all())

    primary_doctor = User.query.get(patient.primary_doctor_id) if patient.primary_doctor_id else None

    pending_appointments = (AppointmentRequest.query
                            .filter_by(patient_id=patient.id)
                            .order_by(AppointmentRequest.created_at.desc())
                            .limit(3).all())

    education_articles = (EducationContent.query
                          .filter_by(status=EducationStatus.APPROVED, published_to_patients=True)
                          .order_by(EducationContent.created_at.desc())
                          .limit(4).all())

    return render_template('dashboard/patient_dashboard.html',
                           patient=patient,
                           recent_vitals=recent_vitals,
                           alerts=alerts,
                           recent_assessments=recent_assessments,
                           primary_doctor=primary_doctor,
                           pending_appointments=pending_appointments,
                           education_articles=education_articles)

@dashboard_bp.route('/health-education')
@login_required
def health_education():
    """Health education resources page"""
    return render_template('dashboard/health_education.html',
                           health_education=health_education_topics)

@dashboard_bp.route('/analytics')
@login_required
def analytics():
    """Analytics and reports"""
    if current_user.role in [UserRole.PATIENT, UserRole.MOTHER]:
        return redirect(url_for('dashboard.patient_dashboard'))

    # Wound healing analytics
    assessments = WoundAssessment.query.all()
    
    # Calculate statistics
    total_assessments = len(assessments)
    excellent = len([a for a in assessments if a.status.value == 'excellent'])
    good = len([a for a in assessments if a.status.value == 'good'])
    fair = len([a for a in assessments if a.status.value == 'fair'])
    poor = len([a for a in assessments if a.status.value == 'poor'])
    infected = len([a for a in assessments if a.status.value == 'infected'])
    
    stats = {
        'total_assessments': total_assessments,
        'excellent': excellent,
        'good': good,
        'fair': fair,
        'poor': poor,
        'infected': infected
    }
    
    return render_template('dashboard/analytics.html', stats=stats)
