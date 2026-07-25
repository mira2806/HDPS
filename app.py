import os
import re
import secrets
from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_login import LoginManager, current_user
from flask_mail import Mail
from models import db, User, NewsletterSubscription, ContactMessage
from auth import auth_bp
from dashboard_routes import admin_bp
from doctor_routes import doctor_bp
from patient_routes import patient_bp

mail = Mail()


def _get_secret_key():
    key_file = os.path.join(os.path.dirname(__file__), '.secret_key')
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_file, 'w') as f:
        f.write(key)
    return key


def create_app():
    base = os.path.dirname(__file__)
    app = Flask(__name__,
                template_folder=os.path.join(base, 'app', 'templates'),
                static_folder=os.path.join(base, 'app', 'static'))

    upload_folder = os.path.join(base, 'app', 'static', 'uploads', 'avatars')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB

    # ---- Security config ------------------------------------------------
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', _get_secret_key())
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # ---- Database -------------------------------------------------------
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Render provides postgres:// but SQLAlchemy requires postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        instance_dir = os.path.join(base, 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            f"sqlite:///{os.path.join(instance_dir, 'hdps.db')}"
        )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ---- Mail -----------------------------------------------------------
    mail_user = os.environ.get('MAIL_USERNAME', 'salamiameer663@gmail.com')
    app.config['MAIL_SERVER']         = 'smtp.gmail.com'
    app.config['MAIL_PORT']           = 587
    app.config['MAIL_USE_TLS']        = True
    app.config['MAIL_USERNAME']       = mail_user
    app.config['MAIL_PASSWORD']       = os.environ.get('MAIL_PASSWORD', 'lycp dxdo egwj zaeu')
    app.config['MAIL_DEFAULT_SENDER'] = ('HeartGuard', mail_user)

    # ---- Extensions -----------------------------------------------------
    db.init_app(app)
    mail.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view         = 'auth.login'
    login_manager.login_message      = 'Please sign in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ---- Blueprints -----------------------------------------------------
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)

    # ---- Public routes --------------------------------------------------
    @app.route('/')
    def index():
        return render_template('index.html')

    # ---- Create tables on first run ------------------------------------
    with app.app_context():
        db.create_all()
        # SQLite-only migration: add avatar column to pre-existing databases
        if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
            with db.engine.connect() as conn:
                try:
                    conn.execute(db.text('ALTER TABLE users ADD COLUMN avatar VARCHAR(200)'))
                    conn.commit()
                except Exception:
                    pass

    # ---- Context processor: inject unread newsletter count -----------
    @app.context_processor
    def inject_globals():
        count = 0
        if current_user.is_authenticated and current_user.role == 'admin':
            count = (NewsletterSubscription.query.filter_by(is_read=False).count() +
                     ContactMessage.query.filter_by(is_read=False).count())
        return {'unread_count': count}

    return app


app = create_app()


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    return render_template('contact.html')


@app.route('/contact/send', methods=['POST'])
def contact_send():
    name    = request.form.get('name', '').strip()
    email   = request.form.get('email', '').strip().lower()
    subject = request.form.get('subject', '').strip()
    message = request.form.get('message', '').strip()
    if not name or not email or not subject or not message:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400
    db.session.add(ContactMessage(name=name, email=email, subject=subject, message=message))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Your message has been sent! We\'ll get back to you shortly.'})


@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email', '').strip().lower()
    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400
    if NewsletterSubscription.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'You are already subscribed!'}), 200
    db.session.add(NewsletterSubscription(email=email))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Thank you for subscribing!'})


if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
