from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db, login_manager, mail
from models import User, Domain, DomainCheck
from utils import check_domain_status, send_notification_email
from datetime import datetime
import urllib.parse
from flask_mail import Message
import secrets

@login_manager.user_loader
def load_user(id):
    return db.session.get(User, int(id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Form validation
        if not all([username, email, password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Send welcome email
            msg = Message(
                'Welcome to Domain Tracker',
                sender='noreply@domaintracker.com',
                recipients=[email]
            )
            msg.body = f'''Welcome to Domain Tracker!
            
Your account has been successfully created.
Username: {username}

You can now login at {request.host_url}login

Thank you for joining us!
'''
            mail.send(msg)
            
            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    domains = Domain.query.filter_by(user_id=current_user.id).all()
    # Get latest status for each domain
    for domain in domains:
        status = check_domain_status(domain.name)
        domain.status = status['status']
        domain.time_info = status['time_info']
        domain.detailed_info = status['detailed_info']
    return render_template('dashboard.html', domains=domains)

@app.route('/domain/add', methods=['POST'])
@login_required
def add_domain():
    domain_name = request.form['domain'].lower()
    parsed = urllib.parse.urlparse(domain_name)
    domain_name = parsed.netloc if parsed.netloc else parsed.path
    
    # Check if domain already exists for user
    existing = Domain.query.filter_by(name=domain_name, user_id=current_user.id).first()
    if existing:
        flash('Domain already exists')
        return redirect(url_for('dashboard'))
    
    tld = domain_name.split('.')[-1]
    domain = Domain(
        name=domain_name,
        user_id=current_user.id,
        tld=tld
    )
    
    status = check_domain_status(domain_name)
    domain.status = status['status']
    domain.registration_date = status.get('registration_date')
    domain.expiration_date = status.get('expiration_date')
    
    db.session.add(domain)
    db.session.flush()
    
    domain_check = DomainCheck(
        domain_id=domain.id,
        status=status['status'],
        response=status['raw_response']
    )
    
    db.session.add(domain_check)
    db.session.commit()
    
    flash('Domain added successfully')
    return redirect(url_for('dashboard'))

@app.route('/domains')
@login_required
def domain_list():
    tld_filter = request.args.get('tld')
    length_filter = request.args.get('length')
    
    query = Domain.query.filter_by(user_id=current_user.id)
    
    if tld_filter:
        query = query.filter_by(tld=tld_filter)
    if length_filter:
        query = query.filter(db.func.length(Domain.name) == int(length_filter))
    
    domains = query.all()
    # Get latest status for each domain
    for domain in domains:
        status = check_domain_status(domain.name)
        domain.status = status['status']
        domain.time_info = status['time_info']
        domain.detailed_info = status['detailed_info']
    
    return render_template('domain_list.html', domains=domains)
