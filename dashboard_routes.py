from functools import wraps
from datetime import date, timedelta
import json, csv, io
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response
from flask_login import login_required, current_user
from models import db, User, Doctor, Patient, Diagnosis, NewsletterSubscription, ContactMessage
from ml import predict as ml_predict

admin_bp = Blueprint('admin', __name__, url_prefix='/dashboard')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access restricted to administrators.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('')
@admin_bp.route('/overview')
@login_required
@admin_required
def overview():
    total_patients  = Patient.query.count()
    total_doctors   = Doctor.query.filter_by(is_active=True).count()
    today_diagnoses = Diagnosis.query.filter(
        db.func.date(Diagnosis.created_at) == date.today()
    ).count()
    high_risk_count = Diagnosis.query.filter_by(risk_level='High').count()

    q = request.args.get('q', '').strip()
    recent_q = (Diagnosis.query
                .join(Patient, Diagnosis.patient_id == Patient.id)
                .join(User,    Patient.user_id == User.id)
                .order_by(Diagnosis.created_at.desc()))
    if q:
        recent_q = recent_q.filter(User.full_name.ilike(f'%{q}%'))
    recent = recent_q.limit(20).all()

    return render_template('dashboard/admin_overview.html',
                           total_patients=total_patients,
                           total_doctors=total_doctors,
                           today_diagnoses=today_diagnoses,
                           high_risk_count=high_risk_count,
                           recent=recent, q=q)


@admin_bp.route('/patients')
@login_required
@admin_required
def patients():
    page = request.args.get('page', 1, type=int)
    q    = request.args.get('q', '').strip()

    query = Patient.query.join(User, Patient.user_id == User.id)
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))
    patients = query.order_by(User.full_name).paginate(page=page, per_page=10, error_out=False)
    doctors  = (Doctor.query.filter_by(is_active=True)
                .join(User, Doctor.user_id == User.id).order_by(User.full_name).all())
    return render_template('dashboard/patients.html', patients=patients, q=q, doctors=doctors)


@admin_bp.route('/doctors')
@login_required
@admin_required
def doctors():
    page = request.args.get('page', 1, type=int)
    q    = request.args.get('q', '').strip()

    query = Doctor.query.join(User, Doctor.user_id == User.id)
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))
    doctors = query.order_by(User.full_name).paginate(page=page, per_page=10, error_out=False)
    return render_template('dashboard/doctors.html', doctors=doctors, q=q)


@admin_bp.route('/detect', methods=['GET', 'POST'])
@login_required
@admin_required
def detect():
    all_patients = (Patient.query
                    .join(User, Patient.user_id == User.id)
                    .order_by(User.full_name).all())
    all_doctors  = (Doctor.query
                    .filter_by(is_active=True)
                    .join(User, Doctor.user_id == User.id)
                    .order_by(User.full_name).all())

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        try:
            f          = request.form
            patient_id = int(f.get('patient_id', 0))
            doctor_id  = int(f.get('doctor_id', 0)) or None

            patient = Patient.query.get(patient_id)
            if not patient:
                if is_ajax:
                    return jsonify({'error': 'Please select a valid patient.'}), 400
                flash('Please select a valid patient.', 'error')
                return redirect(url_for('admin.detect'))

            diag = Diagnosis(
                patient_id = patient_id,
                doctor_id  = doctor_id,
                cp         = int(f.get('cp',      0)),
                thalach    = float(f.get('thalach', 150)),
                exang      = int(f.get('exang',   0)),
                oldpeak    = float(f.get('oldpeak', 0)),
                ca         = int(f.get('ca',      0)),
                thal       = int(f.get('thal',    1)),
            )

            diag.prediction, diag.risk_score, diag.risk_level = ml_predict(
                diag.cp, diag.oldpeak, diag.ca, diag.thalach, diag.thal, diag.exang
            )

            from datetime import datetime
            patient.last_visit = datetime.utcnow()
            if doctor_id:
                patient.doctor_id = doctor_id

            db.session.add(diag)
            db.session.commit()

            if is_ajax:
                return jsonify({
                    'prediction':   diag.prediction,
                    'risk_score':   diag.risk_score,
                    'risk_level':   diag.risk_level,
                    'label':        diag.prediction_label(),
                    'patient_name': patient.user.full_name,
                    'diag_id':      diag.id,
                })

            flash(f'Diagnosis saved. Result: {diag.risk_level} Risk — {diag.prediction_label()}.', 'success')
            return redirect(url_for('admin.results'))

        except (ValueError, TypeError) as e:
            if is_ajax:
                return jsonify({'error': 'Invalid form data. Please check all fields.'}), 400
            flash('Invalid form data. Please check all fields and try again.', 'error')
            return redirect(url_for('admin.detect'))

    return render_template('dashboard/detect.html',
                           all_patients=all_patients,
                           all_doctors=all_doctors)


@admin_bp.route('/results')
@login_required
@admin_required
def results():
    page = request.args.get('page', 1, type=int)
    q    = request.args.get('q', '').strip()

    query = (Diagnosis.query
             .join(Patient, Diagnosis.patient_id == Patient.id)
             .join(User,    Patient.user_id == User.id)
             .order_by(Diagnosis.created_at.desc()))
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))

    results = query.paginate(page=page, per_page=10, error_out=False)
    return render_template('dashboard/results.html', results=results, q=q)


@admin_bp.route('/results/export')
@login_required
@admin_required
def results_export():
    q = request.args.get('q', '').strip()
    query = (Diagnosis.query
             .join(Patient, Diagnosis.patient_id == Patient.id)
             .join(User,    Patient.user_id == User.id)
             .order_by(Diagnosis.created_at.desc()))
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))
    rows = query.all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['ID', 'Patient', 'Age', 'Sex', 'Risk Score (%)', 'Risk Level',
                     'Prediction', 'Doctor', 'Chest Pain Type', 'Max Heart Rate',
                     'Exercise Angina', 'ST Depression', 'Major Vessels', 'Thalassemia', 'Date'])
    cp_map   = {0: 'Typical Angina', 1: 'Atypical Angina', 2: 'Non-Anginal Pain', 3: 'Asymptomatic'}
    thal_map = {1: 'Normal', 2: 'Fixed Defect', 3: 'Reversible Defect'}
    for d in rows:
        writer.writerow([
            d.id,
            d.patient.user.full_name,
            d.age, d.sex_label(),
            round(d.risk_score, 1) if d.risk_score else 0,
            d.risk_level, d.prediction_label(),
            d.doctor.user.full_name if d.doctor else '',
            cp_map.get(d.cp, d.cp),
            d.thalach, 'Yes' if d.exang == 1 else 'No',
            d.oldpeak, d.ca,
            thal_map.get(d.thal, d.thal),
            d.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=diagnosis_results.csv'}
    )


@admin_bp.route('/patients/export')
@login_required
@admin_required
def patients_export():
    q = request.args.get('q', '').strip()
    query = Patient.query.join(User, Patient.user_id == User.id)
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))
    rows = query.order_by(User.full_name).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['ID', 'Full Name', 'Email', 'Age', 'Sex', 'Phone', 'Address',
                     'Assigned Doctor', 'Last Visit', 'Risk Level', 'Diagnoses'])
    for p in rows:
        writer.writerow([
            p.id, p.user.full_name, p.user.email,
            p.age or '', p.sex or '', p.phone or '', p.address or '',
            p.assigned_doctor.user.full_name if p.assigned_doctor else '',
            p.last_visit.strftime('%Y-%m-%d') if p.last_visit else '',
            p.latest_risk_level, p.diagnosis_count,
        ])
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=patients.csv'})


@admin_bp.route('/doctors/export')
@login_required
@admin_required
def doctors_export():
    q = request.args.get('q', '').strip()
    query = Doctor.query.join(User, Doctor.user_id == User.id)
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))
    rows = query.order_by(User.full_name).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['ID', 'Full Name', 'Email', 'Specialty', 'Phone',
                     'Status', 'Patients', 'Diagnoses', 'Joined'])
    for d in rows:
        writer.writerow([
            d.id, d.user.full_name, d.user.email,
            d.specialty or '', d.phone or '',
            'Active' if d.is_active else 'Inactive',
            d.patient_count, d.diagnosis_count,
            d.user.created_at.strftime('%Y-%m-%d'),
        ])
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=doctors.csv'})


@admin_bp.route('/analysis')
@login_required
@admin_required
def analysis():
    total_diagnoses = Diagnosis.query.count()
    positive_cases  = Diagnosis.query.filter_by(prediction=1).count()
    negative_cases  = Diagnosis.query.filter_by(prediction=0).count()
    positive_rate   = round((positive_cases / total_diagnoses * 100) if total_diagnoses else 0, 1)

    avg_row   = db.session.execute(db.select(db.func.avg(Diagnosis.risk_score))).fetchone()
    avg_score = round(avg_row[0] or 0, 1)

    # Risk level counts
    risk_data = {
        'High':   Diagnosis.query.filter_by(risk_level='High').count(),
        'Medium': Diagnosis.query.filter_by(risk_level='Medium').count(),
        'Low':    Diagnosis.query.filter_by(risk_level='Low').count(),
    }

    # Daily diagnoses — last 30 days (fill zeros for missing dates)
    thirty_ago = date.today() - timedelta(days=29)
    daily_rows = (db.session.query(
        db.func.date(Diagnosis.created_at).label('day'),
        db.func.count().label('cnt')
    ).filter(db.func.date(Diagnosis.created_at) >= thirty_ago.isoformat())
     .group_by('day').order_by('day').all())
    day_map = {str(r.day): r.cnt for r in daily_rows}
    daily_labels, daily_values = [], []
    for i in range(30):
        d = thirty_ago + timedelta(days=i)
        daily_labels.append(d.strftime('%b %d'))
        daily_values.append(day_map.get(d.isoformat(), 0))

    # Monthly trend — last 6 months
    monthly_rows = (db.session.query(
        db.func.strftime('%Y-%m', Diagnosis.created_at).label('month'),
        db.func.count().label('cnt')
    ).group_by('month').order_by('month').all())[-6:]
    month_labels = [r.month for r in monthly_rows]
    month_values = [r.cnt  for r in monthly_rows]

    # Age group distribution
    all_diags = Diagnosis.query.with_entities(Diagnosis.age, Diagnosis.prediction).all()
    age_groups = {'<30': 0, '30-39': 0, '40-49': 0, '50-59': 0, '60-69': 0, '70+': 0}
    for row in all_diags:
        age = row.age or 0
        if   age < 30: age_groups['<30']   += 1
        elif age < 40: age_groups['30-39'] += 1
        elif age < 50: age_groups['40-49'] += 1
        elif age < 60: age_groups['50-59'] += 1
        elif age < 70: age_groups['60-69'] += 1
        else:          age_groups['70+']   += 1

    # Sex distribution
    male_total   = Diagnosis.query.filter_by(sex=1).count()
    female_total = Diagnosis.query.filter_by(sex=0).count()
    male_pos     = Diagnosis.query.filter_by(sex=1, prediction=1).count()
    female_pos   = Diagnosis.query.filter_by(sex=0, prediction=1).count()

    # Chest pain type distribution
    cp_labels = ['Typical Angina', 'Atypical Angina', 'Non-Anginal Pain', 'Asymptomatic']
    cp_values = [Diagnosis.query.filter_by(cp=i).count() for i in range(4)]

    # Top 5 doctors by diagnosis count
    top_docs = (db.session.query(User.full_name, db.func.count(Diagnosis.id).label('cnt'))
                .join(Doctor,    Doctor.user_id    == User.id)
                .join(Diagnosis, Diagnosis.doctor_id == Doctor.id)
                .group_by(User.id)
                .order_by(db.text('cnt DESC'))
                .limit(5).all())

    # Cholesterol risk buckets
    chol_ranges  = ['<200', '200-239', '240-279', '280+']
    chol_buckets = [
        Diagnosis.query.filter(Diagnosis.chol < 200).count(),
        Diagnosis.query.filter(Diagnosis.chol.between(200, 239)).count(),
        Diagnosis.query.filter(Diagnosis.chol.between(240, 279)).count(),
        Diagnosis.query.filter(Diagnosis.chol >= 280).count(),
    ]

    return render_template('dashboard/analysis.html',
        total_diagnoses = total_diagnoses,
        positive_cases  = positive_cases,
        negative_cases  = negative_cases,
        positive_rate   = positive_rate,
        avg_score       = avg_score,
        risk_json       = json.dumps(risk_data),
        daily_labels    = json.dumps(daily_labels),
        daily_values    = json.dumps(daily_values),
        month_labels    = json.dumps(month_labels),
        month_values    = json.dumps(month_values),
        age_labels      = json.dumps(list(age_groups.keys())),
        age_values      = json.dumps(list(age_groups.values())),
        sex_labels      = json.dumps(['Male', 'Female']),
        sex_values      = json.dumps([male_total, female_total]),
        sex_pos         = json.dumps([male_pos, female_pos]),
        cp_labels       = json.dumps(cp_labels),
        cp_values       = json.dumps(cp_values),
        doc_labels      = json.dumps([r.full_name for r in top_docs]),
        doc_values      = json.dumps([r.cnt for r in top_docs]),
        chol_labels     = json.dumps(chol_ranges),
        chol_values     = json.dumps(chol_buckets),
        active_page     = 'analysis',
        active_group    = '',
    )


## ── JSON API: patients ─────────────────────────────────────────────────

@admin_bp.route('/api/patients/<int:pid>')
@login_required
@admin_required
def api_patient(pid):
    p = Patient.query.get_or_404(pid)
    all_docs = (Doctor.query.filter_by(is_active=True)
                .join(User, Doctor.user_id == User.id).order_by(User.full_name).all())
    return jsonify({
        'id': p.id, 'initials': p.user.get_initials(),
        'full_name': p.user.full_name, 'email': p.user.email,
        'age': p.age, 'sex': p.sex, 'phone': p.phone or '',
        'address': p.address or '',
        'last_visit': p.last_visit.strftime('%b %d, %Y') if p.last_visit else '—',
        'risk_level': p.latest_risk_level,
        'diagnosis_count': p.diagnosis_count,
        'doctor_id': p.doctor_id,
        'doctor_name': p.assigned_doctor.user.full_name if p.assigned_doctor else '—',
        'doctors': [{'id': d.id, 'name': d.user.full_name} for d in all_docs],
    })


@admin_bp.route('/api/patients/<int:pid>/update', methods=['POST'])
@login_required
@admin_required
def api_patient_update(pid):
    p = Patient.query.get_or_404(pid)
    f = request.form
    p.user.full_name = (f.get('full_name') or p.user.full_name).strip()
    p.user.email     = (f.get('email') or p.user.email).strip().lower()
    p.age            = int(f.get('age')) if f.get('age') else p.age
    p.sex            = f.get('sex') or p.sex
    p.phone          = f.get('phone', '').strip() or None
    p.address        = f.get('address', '').strip() or None
    p.doctor_id      = int(f.get('doctor_id')) if f.get('doctor_id') else None
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/api/patients/<int:pid>/delete', methods=['POST'])
@login_required
@admin_required
def api_patient_delete(pid):
    p = Patient.query.get_or_404(pid)
    user = p.user
    db.session.delete(p)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/api/patients/add', methods=['POST'])
@login_required
@admin_required
def api_patient_add():
    f = request.form
    full_name = (f.get('full_name') or '').strip()
    email     = (f.get('email') or '').strip().lower()
    password  = (f.get('password') or '').strip()

    if not full_name or not email or not password:
        return jsonify({'success': False, 'error': 'Full name, email and password are required.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'A user with this email already exists.'}), 400

    user = User(full_name=full_name, email=email, role='patient')
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    patient = Patient(
        user_id   = user.id,
        age       = int(f.get('age')) if f.get('age') else None,
        sex       = f.get('sex') or None,
        phone     = f.get('phone', '').strip() or None,
        address   = f.get('address', '').strip() or None,
        doctor_id = int(f.get('doctor_id')) if f.get('doctor_id') else None,
    )
    db.session.add(patient)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Patient {full_name} added successfully.'})


## ── JSON API: doctors ──────────────────────────────────────────────────

@admin_bp.route('/api/doctors/add', methods=['POST'])
@login_required
@admin_required
def api_doctor_add():
    f = request.form
    full_name = (f.get('full_name') or '').strip()
    email     = (f.get('email') or '').strip().lower()
    password  = (f.get('password') or '').strip()

    if not full_name or not email or not password:
        return jsonify({'success': False, 'error': 'Full name, email and password are required.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'A user with this email already exists.'}), 400

    user = User(full_name=full_name, email=email, role='doctor')
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    doctor = Doctor(
        user_id   = user.id,
        specialty = (f.get('specialty') or '').strip() or 'General Physician',
        phone     = f.get('phone', '').strip() or None,
        is_active = True,
    )
    db.session.add(doctor)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Doctor {full_name} added successfully.'})


@admin_bp.route('/api/doctors/<int:did>')
@login_required
@admin_required
def api_doctor(did):
    d = Doctor.query.get_or_404(did)
    return jsonify({
        'id': d.id, 'initials': d.user.get_initials(),
        'full_name': d.user.full_name, 'email': d.user.email,
        'specialty': d.specialty or '', 'phone': d.phone or '',
        'patient_count': d.patient_count, 'diagnosis_count': d.diagnosis_count,
        'is_active': d.is_active,
        'joined': d.user.created_at.strftime('%b %d, %Y'),
    })


@admin_bp.route('/api/doctors/<int:did>/update', methods=['POST'])
@login_required
@admin_required
def api_doctor_update(did):
    d = Doctor.query.get_or_404(did)
    f = request.form
    d.user.full_name = (f.get('full_name') or d.user.full_name).strip()
    d.user.email     = (f.get('email') or d.user.email).strip().lower()
    d.specialty      = f.get('specialty', '').strip() or d.specialty
    d.phone          = f.get('phone', '').strip() or None
    d.is_active      = f.get('is_active', '1') == '1'
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/api/doctors/<int:did>/delete', methods=['POST'])
@login_required
@admin_required
def api_doctor_delete(did):
    d = Doctor.query.get_or_404(did)
    user = d.user
    db.session.delete(d)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True})


## ── JSON API: diagnosis results ────────────────────────────────────────

@admin_bp.route('/api/results/<int:rid>')
@login_required
@admin_required
def api_result(rid):
    d = Diagnosis.query.get_or_404(rid)
    cp_map   = {0:'Typical Angina', 1:'Atypical Angina', 2:'Non-Anginal Pain', 3:'Asymptomatic'}
    thal_map = {1:'Normal', 2:'Fixed Defect', 3:'Reversible Defect'}
    return jsonify({
        'id': d.id,
        'patient_name': d.patient.user.full_name,
        'doctor_name':  d.doctor.user.full_name if d.doctor else '—',
        'risk_score': round(d.risk_score, 1) if d.risk_score else 0,
        'risk_level': d.risk_level,
        'prediction_label': d.prediction_label(),
        'cp':     cp_map.get(d.cp, str(d.cp)),
        'thalach': d.thalach, 'oldpeak': d.oldpeak, 'ca': d.ca,
        'exang':  'Yes' if d.exang == 1 else 'No',
        'thal':   thal_map.get(d.thal, str(d.thal)),
        'created_at': d.created_at.strftime('%b %d, %Y · %H:%M'),
    })


@admin_bp.route('/api/results/<int:rid>/delete', methods=['POST'])
@login_required
@admin_required
def api_result_delete(rid):
    d = Diagnosis.query.get_or_404(rid)
    db.session.delete(d)
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/messages')
@login_required
@admin_required
def messages():
    subs   = NewsletterSubscription.query.order_by(NewsletterSubscription.subscribed_at.desc()).all()
    contacts = ContactMessage.query.order_by(ContactMessage.sent_at.desc()).all()
    unread_subs     = NewsletterSubscription.query.filter_by(is_read=False).count()
    unread_contacts = ContactMessage.query.filter_by(is_read=False).count()
    return render_template('dashboard/messages.html',
                           subs=subs, contacts=contacts,
                           unread_subs=unread_subs, unread_contacts=unread_contacts,
                           unread=unread_subs + unread_contacts,
                           active_page='messages', active_group='')


@admin_bp.route('/messages/newsletter/<int:sub_id>/read', methods=['POST'])
@login_required
@admin_required
def mark_read(sub_id):
    sub = NewsletterSubscription.query.get_or_404(sub_id)
    sub.is_read = True
    db.session.commit()
    remaining = (NewsletterSubscription.query.filter_by(is_read=False).count() +
                 ContactMessage.query.filter_by(is_read=False).count())
    return jsonify({'success': True, 'remaining': remaining})


@admin_bp.route('/messages/contact/<int:msg_id>/read', methods=['POST'])
@login_required
@admin_required
def mark_contact_read(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    msg.is_read = True
    db.session.commit()
    remaining = (NewsletterSubscription.query.filter_by(is_read=False).count() +
                 ContactMessage.query.filter_by(is_read=False).count())
    return jsonify({'success': True, 'remaining': remaining})


@admin_bp.route('/messages/contact/<int:msg_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_contact_message(msg_id):
    msg = ContactMessage.query.get_or_404(msg_id)
    db.session.delete(msg)
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/messages/read-all', methods=['POST'])
@login_required
@admin_required
def mark_all_read():
    NewsletterSubscription.query.filter_by(is_read=False).update({'is_read': True})
    ContactMessage.query.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


@admin_bp.route('/report')
@login_required
@admin_required
def report():
    total_diagnoses = Diagnosis.query.count()
    total_patients  = Patient.query.count()
    total_doctors   = Doctor.query.filter_by(is_active=True).count()
    positive_cases  = Diagnosis.query.filter_by(prediction=1).count()
    negative_cases  = Diagnosis.query.filter_by(prediction=0).count()

    high_count   = Diagnosis.query.filter_by(risk_level='High').count()
    medium_count = Diagnosis.query.filter_by(risk_level='Medium').count()
    low_count    = Diagnosis.query.filter_by(risk_level='Low').count()

    def pct(n): return round((n / total_diagnoses * 100) if total_diagnoses else 0, 1)

    high_pct   = pct(high_count)
    medium_pct = pct(medium_count)
    low_pct    = pct(low_count)
    pos_rate   = pct(positive_cases)

    # Monthly breakdown — aggregate in Python for simplicity
    all_diags = Diagnosis.query.order_by(Diagnosis.created_at).all()
    monthly_raw = {}
    for d in all_diags:
        key   = d.created_at.strftime('%Y-%m')   if d.created_at else 'Unknown'
        label = d.created_at.strftime('%B %Y')   if d.created_at else 'Unknown'
        if key not in monthly_raw:
            monthly_raw[key] = dict(label=label, total=0, high=0, medium=0, low=0, pos=0, neg=0)
        monthly_raw[key]['total'] += 1
        if   d.risk_level == 'High':   monthly_raw[key]['high']   += 1
        elif d.risk_level == 'Medium': monthly_raw[key]['medium'] += 1
        elif d.risk_level == 'Low':    monthly_raw[key]['low']    += 1
        if d.prediction == 1: monthly_raw[key]['pos'] += 1
        else:                 monthly_raw[key]['neg'] += 1
    monthly = [v for _, v in sorted(monthly_raw.items())]

    # Totals row for tfoot
    totals = dict(
        total  = sum(r['total']  for r in monthly),
        high   = sum(r['high']   for r in monthly),
        medium = sum(r['medium'] for r in monthly),
        low    = sum(r['low']    for r in monthly),
        pos    = sum(r['pos']    for r in monthly),
        neg    = sum(r['neg']    for r in monthly),
    )

    # Top 5 doctors by diagnosis count
    top_doctors = (
        db.session.query(User.full_name, Doctor.specialty,
                         db.func.count(Diagnosis.id).label('cnt'))
        .join(Doctor,    Doctor.user_id    == User.id)
        .join(Diagnosis, Diagnosis.doctor_id == Doctor.id)
        .group_by(Doctor.id)
        .order_by(db.text('cnt DESC'))
        .limit(5).all()
    )

    # Recent high-risk cases
    recent_high = (Diagnosis.query
                   .filter_by(risk_level='High')
                   .order_by(Diagnosis.created_at.desc())
                   .limit(5).all())

    return render_template('dashboard/report.html',
        total_diagnoses = total_diagnoses,
        total_patients  = total_patients,
        total_doctors   = total_doctors,
        positive_cases  = positive_cases,
        negative_cases  = negative_cases,
        high_count      = high_count,
        medium_count    = medium_count,
        low_count       = low_count,
        high_pct        = high_pct,
        medium_pct      = medium_pct,
        low_pct         = low_pct,
        pos_rate        = pos_rate,
        monthly         = monthly,
        totals          = totals,
        top_doctors     = top_doctors,
        recent_high     = recent_high,
    )
