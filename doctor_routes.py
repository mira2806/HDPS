from functools import wraps
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Patient, Diagnosis, User, Doctor
from ml import predict as ml_predict

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')


def doctor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'doctor':
            flash('Access restricted to doctors.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@doctor_bp.route('/dashboard')
@login_required
@doctor_required
def dashboard():
    doctor  = current_user.doctor_profile
    p_count = doctor.patients.count() if doctor else 0
    d_count = doctor.diagnoses.count() if doctor else 0
    today   = doctor.diagnoses.filter(
                  db.func.date(Diagnosis.created_at) == date.today()
              ).count() if doctor else 0
    recent  = (doctor.diagnoses.order_by(Diagnosis.created_at.desc()).limit(6).all()
               if doctor else [])
    return render_template('doctor/dashboard.html',
                           doctor=doctor,
                           p_count=p_count,
                           d_count=d_count,
                           today=today,
                           recent=recent,
                           active_page='doctor_home',
                           active_group='')


@doctor_bp.route('/patients')
@login_required
@doctor_required
def patients():
    doctor = current_user.doctor_profile
    q      = request.args.get('q', '').strip()
    page   = request.args.get('page', 1, type=int)

    query = (doctor.patients.join(User, Patient.user_id == User.id)
             if doctor else Patient.query.filter_by(id=None))
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))
    patients = query.order_by(User.full_name).paginate(page=page, per_page=10, error_out=False)

    return render_template('doctor/patients.html',
                           patients=patients,
                           q=q,
                           active_page='doctor_patients',
                           active_group='doctor_patients')


@doctor_bp.route('/detect', methods=['GET', 'POST'])
@login_required
@doctor_required
def detect():
    doctor      = current_user.doctor_profile
    all_patients = (doctor.patients.join(User, Patient.user_id == User.id)
                    .order_by(User.full_name).all() if doctor else [])

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        try:
            f          = request.form
            patient_id = int(f.get('patient_id', 0))
            patient    = Patient.query.get(patient_id)

            if not patient:
                if is_ajax:
                    return jsonify({'error': 'Please select a valid patient.'}), 400
                flash('Please select a valid patient.', 'error')
                return redirect(url_for('doctor.detect'))

            diag = Diagnosis(
                patient_id = patient_id,
                doctor_id  = doctor.id if doctor else None,
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

            flash(f'Diagnosis saved — {diag.risk_level} Risk, {diag.prediction_label()}.', 'success')
            return redirect(url_for('doctor.results'))

        except (ValueError, TypeError):
            if is_ajax:
                return jsonify({'error': 'Invalid form data. Please check all fields.'}), 400
            flash('Invalid form data. Please check all fields.', 'error')
            return redirect(url_for('doctor.detect'))

    return render_template('doctor/detect.html',
                           all_patients=all_patients,
                           active_page='doctor_detect',
                           active_group='doctor_detect')


@doctor_bp.route('/api/patients/<int:pid>')
@login_required
@doctor_required
def api_patient(pid):
    p = Patient.query.get_or_404(pid)
    return jsonify({
        'id': p.id, 'initials': p.user.get_initials(),
        'full_name': p.user.full_name, 'email': p.user.email,
        'age': p.age, 'sex': p.sex, 'phone': p.phone or '',
        'address': p.address or '',
        'last_visit': p.last_visit.strftime('%b %d, %Y') if p.last_visit else '—',
        'risk_level': p.latest_risk_level,
        'diagnosis_count': p.diagnosis_count,
        'doctor_name': p.assigned_doctor.user.full_name if p.assigned_doctor else '—',
        'doctors': [],
    })


@doctor_bp.route('/api/results/<int:rid>')
@login_required
@doctor_required
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


@doctor_bp.route('/api/results/<int:rid>/delete', methods=['POST'])
@login_required
@doctor_required
def api_result_delete(rid):
    d = Diagnosis.query.get_or_404(rid)
    db.session.delete(d)
    db.session.commit()
    return jsonify({'success': True})


@doctor_bp.route('/results')
@login_required
@doctor_required
def results():
    doctor = current_user.doctor_profile
    q      = request.args.get('q', '').strip()
    page   = request.args.get('page', 1, type=int)

    query = (doctor.diagnoses
             .join(Patient, Diagnosis.patient_id == Patient.id)
             .join(User,    Patient.user_id == User.id)
             .order_by(Diagnosis.created_at.desc())
             if doctor else Diagnosis.query.filter_by(id=None))
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))
    results = query.paginate(page=page, per_page=10, error_out=False)

    return render_template('doctor/results.html',
                           results=results,
                           q=q,
                           active_page='doctor_results',
                           active_group='doctor_detect')
