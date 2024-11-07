from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db, login_manager
from models import User, Domain, DomainCheck
from utils import check_domain_status, send_notification_email
from datetime import datetime
import urllib.parse

@login_manager.user_loader
def load_user(id):
    return db.session.get(User, int(id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
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
    domains = Domain.query.filter_by(user_id=current_user.id)
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
    return render_template('domain_list.html', domains=domains)
