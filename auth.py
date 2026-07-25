import re, os, base64
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Message
from models import db, User, Doctor, Patient

_AVATAR_EXTS = {'png', 'jpg', 'jpeg', 'webp', 'jfif'}

def _allowed_avatar(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in _AVATAR_EXTS


auth_bp = Blueprint('auth', __name__)

ADMIN_SECRET = 'HDPS-ADMIN-2026'


def _valid_email(email):
    return re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email) is not None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password. Please try again.', 'error')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash('Your account is deactivated. Contact support.', 'error')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        flash(f'Welcome back, {user.full_name.split()[0]}!', 'success')

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return _redirect_by_role(user.role)

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == 'POST':
        full_name   = request.form.get('full_name', '').strip()
        email       = request.form.get('email', '').strip().lower()
        password    = request.form.get('password', '')
        confirm_pwd = request.form.get('confirm_password', '')
        role        = request.form.get('role', 'patient')
        specialty   = request.form.get('specialty', 'General Physician').strip() or 'General Physician'
        admin_code  = request.form.get('admin_code', '').strip()
        terms       = request.form.get('terms')

        if not full_name or len(full_name) < 2:
            flash('Please enter your full name (at least 2 characters).', 'error')
            return redirect(url_for('auth.register'))

        if not _valid_email(email):
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return redirect(url_for('auth.register'))

        if password != confirm_pwd:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))

        if role not in ('admin', 'doctor', 'patient'):
            flash('Please select a valid account type.', 'error')
            return redirect(url_for('auth.register'))

        if role == 'admin' and admin_code != ADMIN_SECRET:
            flash('Invalid admin access code.', 'error')
            return redirect(url_for('auth.register'))

        if not terms:
            flash('You must accept the Terms of Service to continue.', 'error')
            return redirect(url_for('auth.register'))

        user = User(full_name=full_name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        if role == 'doctor':
            db.session.add(Doctor(user_id=user.id, specialty=specialty))
        elif role == 'patient':
            db.session.add(Patient(user_id=user.id))

        db.session.commit()
        flash('Account created successfully! Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    name = current_user.full_name.split()[0]
    logout_user()
    flash(f'You have signed out successfully, {name}!', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/account/settings', methods=['GET', 'POST'])
@login_required
def account_settings():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'profile':
            full_name = request.form.get('full_name', '').strip()
            email     = request.form.get('email', '').strip().lower()
            if not full_name or len(full_name) < 2:
                flash('Full name must be at least 2 characters.', 'error')
                return redirect(url_for('auth.account_settings'))
            if not _valid_email(email):
                flash('Please enter a valid email address.', 'error')
                return redirect(url_for('auth.account_settings'))
            taken = User.query.filter_by(email=email).first()
            if taken and taken.id != current_user.id:
                flash('That email is already in use by another account.', 'error')
                return redirect(url_for('auth.account_settings'))
            current_user.full_name = full_name
            current_user.email     = email
            db.session.commit()
            flash('Profile updated successfully.', 'success')

        elif action == 'password':
            current_pwd  = request.form.get('current_password', '')
            new_pwd      = request.form.get('new_password', '')
            confirm_pwd  = request.form.get('confirm_password', '')
            if not current_user.check_password(current_pwd):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('auth.account_settings'))
            if len(new_pwd) < 8:
                flash('New password must be at least 8 characters.', 'error')
                return redirect(url_for('auth.account_settings'))
            if new_pwd != confirm_pwd:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('auth.account_settings'))
            current_user.set_password(new_pwd)
            db.session.commit()
            flash('Password updated successfully.', 'success')

    return render_template('dashboard/settings.html',
                           active_page='settings', active_group='')


def _make_reset_token(email):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(email, salt='pw-reset')

def _verify_reset_token(token, max_age=3600):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        return s.loads(token, salt='pw-reset', max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email).first()
        # Always show the same message to prevent email enumeration
        if user:
            token     = _make_reset_token(user.email)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            from app import mail
            logo_path = os.path.join(current_app.static_folder, 'images', 'systemLogo.png')
            logo_data_uri = ''
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_data_uri = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
            html_body = render_template('email/reset_password.html',
                                        user=user, reset_url=reset_url,
                                        logo_data_uri=logo_data_uri)
            msg = Message(subject='Reset your HeartGuard password',
                          recipients=[user.email],
                          html=html_body)
            try:
                mail.send(msg)
            except Exception as e:
                current_app.logger.error(f'Mail error: {e}')
                flash('Could not send email. Please try again later.', 'error')
                return redirect(url_for('auth.forgot_password'))
        flash('If that email is registered, a reset link has been sent. Check your inbox.', 'info')
        return redirect(url_for('auth.forgot_password'))
    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)
    email = _verify_reset_token(token)
    if not email:
        flash('This reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        new_pwd     = request.form.get('new_password', '')
        confirm_pwd = request.form.get('confirm_password', '')
        if len(new_pwd) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return redirect(request.url)
        if new_pwd != confirm_pwd:
            flash('Passwords do not match.', 'error')
            return redirect(request.url)
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Account not found.', 'error')
            return redirect(url_for('auth.forgot_password'))
        user.set_password(new_pwd)
        db.session.commit()
        flash('Password updated successfully! You can now sign in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', token=token)


@auth_bp.route('/account/avatar', methods=['POST'])
@login_required
def upload_avatar():
    file = request.files.get('avatar')
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected.'})
    if not _allowed_avatar(file.filename):
        return jsonify({'success': False, 'message': 'Only PNG, JPG, JPEG, WEBP, JFIF allowed.'})
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f'user_{current_user.id}.{ext}'
    folder = current_app.config['UPLOAD_FOLDER']
    # Remove any previous avatar for this user
    for old_ext in _AVATAR_EXTS:
        old = os.path.join(folder, f'user_{current_user.id}.{old_ext}')
        if os.path.exists(old):
            os.remove(old)
    file.save(os.path.join(folder, filename))
    current_user.avatar = filename
    db.session.commit()
    return jsonify({
        'success': True,
        'url': url_for('static', filename=f'uploads/avatars/{filename}')
    })


def _redirect_by_role(role):
    if role == 'admin':
        return redirect(url_for('admin.overview'))
    elif role == 'doctor':
        return redirect(url_for('doctor.dashboard'))
    return redirect(url_for('patient.dashboard'))
