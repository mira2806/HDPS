from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    full_name     = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default='patient')
    active        = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    avatar        = db.Column(db.String(200), nullable=True)

    doctor_profile  = db.relationship('Doctor',  backref='user', uselist=False,
                                       cascade='all, delete-orphan')
    patient_profile = db.relationship('Patient', backref='user', uselist=False,
                                       cascade='all, delete-orphan')

    # Flask-Login requires is_active
    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256:600000'
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_initials(self):
        parts = self.full_name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.full_name[:2].upper()

    def role_label(self):
        return {'admin': 'Administrator', 'doctor': 'Doctor',
                'patient': 'Patient'}.get(self.role, self.role.title())


class Doctor(db.Model):
    __tablename__ = 'doctors'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    specialty  = db.Column(db.String(100), default='General Physician')
    phone      = db.Column(db.String(20))
    is_active  = db.Column(db.Boolean, default=True)

    patients  = db.relationship('Patient', backref='assigned_doctor', lazy='dynamic',
                                 foreign_keys='Patient.doctor_id')
    diagnoses = db.relationship('Diagnosis', backref='doctor', lazy='dynamic',
                                 foreign_keys='Diagnosis.doctor_id')

    @property
    def patient_count(self):
        return self.patients.count()

    @property
    def diagnosis_count(self):
        return self.diagnoses.count()


class Patient(db.Model):
    __tablename__ = 'patients'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    doctor_id  = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)
    age        = db.Column(db.Integer)
    sex        = db.Column(db.String(10))
    phone      = db.Column(db.String(20))
    address    = db.Column(db.String(200))
    last_visit = db.Column(db.DateTime)

    diagnoses = db.relationship('Diagnosis', backref='patient', lazy='dynamic',
                                 foreign_keys='Diagnosis.patient_id')

    @property
    def latest_risk_level(self):
        from models import Diagnosis
        d = self.diagnoses.order_by(Diagnosis.created_at.desc()).first()
        return d.risk_level if d else '—'

    @property
    def diagnosis_count(self):
        return self.diagnoses.count()


class Diagnosis(db.Model):
    __tablename__ = 'diagnoses'

    id         = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id  = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)

    # 13 clinical features
    age      = db.Column(db.Integer)
    sex      = db.Column(db.Integer)       # 0=Female 1=Male
    cp       = db.Column(db.Integer)
    trestbps = db.Column(db.Float)
    chol     = db.Column(db.Float)
    fbs      = db.Column(db.Integer)
    restecg  = db.Column(db.Integer)
    thalach  = db.Column(db.Float)
    exang    = db.Column(db.Integer)
    oldpeak  = db.Column(db.Float)
    slope    = db.Column(db.Integer)
    ca       = db.Column(db.Integer)
    thal     = db.Column(db.Integer)

    # Results
    prediction = db.Column(db.Integer)    # 0=No disease  1=Heart disease
    risk_score = db.Column(db.Float)
    risk_level = db.Column(db.String(20)) # High / Medium / Low
    notes      = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def sex_label(self):
        return 'Male' if self.sex == 1 else 'Female'

    def prediction_label(self):
        return 'Heart Disease' if self.prediction == 1 else 'No Heart Disease'


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), nullable=False)
    subject    = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    sent_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_read    = db.Column(db.Boolean, default=False, nullable=False)


class NewsletterSubscription(db.Model):
    __tablename__ = 'newsletter_subscriptions'

    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_read       = db.Column(db.Boolean, default=False, nullable=False)
