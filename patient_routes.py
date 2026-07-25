from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Diagnosis

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')


def patient_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'patient':
            flash('Access restricted to patients.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@patient_bp.route('/dashboard')
@login_required
@patient_required
def dashboard():
    profile  = current_user.patient_profile
    results  = (profile.diagnoses.order_by(Diagnosis.created_at.desc()).all()
                if profile else [])
    return render_template('patient/dashboard.html',
                           profile=profile,
                           results=results,
                           active_page='patient_home')


@patient_bp.route('/api/diagnosis/<int:did>')
@login_required
@patient_required
def api_diagnosis(did):
    profile = current_user.patient_profile
    if not profile:
        return jsonify({'error': 'Not found'}), 404
    d = Diagnosis.query.filter_by(id=did, patient_id=profile.id).first_or_404()
    cp_map   = {0: 'Typical Angina', 1: 'Atypical Angina', 2: 'Non-Anginal Pain', 3: 'Asymptomatic'}
    thal_map = {1: 'Normal', 2: 'Fixed Defect', 3: 'Reversible Defect'}
    return jsonify({
        'id': d.id,
        'date': d.created_at.strftime('%B %d, %Y'),
        'age': d.age, 'sex': d.sex_label(),
        'risk_score': round(d.risk_score, 1) if d.risk_score else 0,
        'risk_level': d.risk_level,
        'prediction': d.prediction_label(),
        'doctor': d.doctor.user.full_name if d.doctor else '—',
        'cp': cp_map.get(d.cp, '—'),
        'trestbps': d.trestbps, 'chol': d.chol,
        'fbs': 'Yes' if d.fbs == 1 else 'No',
        'restecg': d.restecg, 'thalach': d.thalach,
        'exang': 'Yes' if d.exang == 1 else 'No',
        'oldpeak': d.oldpeak, 'slope': d.slope,
        'ca': d.ca, 'thal': thal_map.get(d.thal, '—'),
        'notes': d.notes or '',
    })
