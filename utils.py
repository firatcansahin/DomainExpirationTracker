import whois
from datetime import datetime, timedelta
from flask_mail import Message
from app import mail, db
from models import Domain
import socket

def calculate_time_remaining(date):
    if not date:
        return None
    if isinstance(date, list):
        date = date[0]
    today = datetime.now()
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return None
    time_diff = date - today
    return time_diff.days

def format_time_status(days):
    if not days:
        return "Unknown"
    if days < 0:
        return "Expired"
    if days <= 5:
        return f"Warning: {days} days remaining"
    return f"{days} days remaining"

def format_availability_date(days):
    if not days:
        return "Unknown"
    if days < 0:
        return "Available now"
    return f"Available in {days} days"

def check_domain_status(domain_name):
    try:
        w = whois.whois(domain_name)
        
        # Get dates
        expiration_date = w.expiration_date[0] if isinstance(w.expiration_date, list) else w.expiration_date
        registration_date = w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date
        
        # Calculate time remaining
        days_remaining = calculate_time_remaining(expiration_date)
        
        # Determine status and availability
        if w.status and isinstance(w.status, list):
            status_text = w.status[0].lower()
        else:
            status_text = str(w.status).lower() if w.status else ''

        # Calculate availability date for pendingDelete domains
        availability_date = None
        if 'pendingdelete' in status_text:
            status = 'PendingDelete'
            availability_date = datetime.now() + timedelta(days=5)
            time_info = format_availability_date(5)  # Standard 5-day redemption period
        else:
            if days_remaining and days_remaining <= 5:
                status = 'Expiring Soon'
            else:
                status = 'Active' if days_remaining and days_remaining > 0 else 'Expired'
            time_info = format_time_status(days_remaining)

        # Construct detailed status information
        detailed_info = {
            'registrar': w.registrar,
            'whois_server': w.whois_server,
            'name_servers': w.name_servers if isinstance(w.name_servers, list) else [w.name_servers] if w.name_servers else [],
            'dnssec': getattr(w, 'dnssec', 'Unknown'),
            'status_codes': w.status if isinstance(w.status, list) else [w.status] if w.status else [],
            'availability_date': availability_date.strftime('%Y-%m-%d') if availability_date else None
        }

        return {
            'status': status,
            'registration_date': registration_date,
            'expiration_date': expiration_date,
            'time_info': time_info,
            'detailed_info': detailed_info,
            'raw_response': str(w),
            'needs_warning': days_remaining is not None and days_remaining <= 5
        }
    except Exception as e:
        return {
            'status': 'Error',
            'registration_date': None,
            'expiration_date': None,
            'time_info': 'Unable to check',
            'detailed_info': {'error': str(e)},
            'raw_response': str(e),
            'needs_warning': False
        }

def send_notification_email(user_email, domain_name, status_change, expiration_date=None):
    subject = 'Domain Status Change Notification'
    body = f"""
    Domain Status Change Alert
    
    Domain: {domain_name}
    Status: {status_change}
    """
    
    if expiration_date:
        body += f"\nExpiration Date: {expiration_date.strftime('%Y-%m-%d')}"
        if isinstance(status_change, str) and "expiring" in status_change.lower():
            subject = 'Domain Expiration Warning'
            body += "\n\nPlease take action to renew your domain before it expires."
    
    body += f"\nTime: {datetime.utcnow()}"
    
    msg = Message(
        subject,
        sender='noreply@domaintracker.com',
        recipients=[user_email]
    )
    msg.body = body
    mail.send(msg)

def check_expiring_domains():
    """Background task to check for expiring domains and send notifications"""
    try:
        # Query domains expiring within 5 days
        expiring_soon = Domain.query.filter(
            Domain.expiration_date <= datetime.now() + timedelta(days=5),
            Domain.expiration_date > datetime.now()
        ).all()
        
        for domain in expiring_soon:
            # Check current status
            status = check_domain_status(domain.name)
            if status['needs_warning']:
                send_notification_email(
                    domain.owner.email,
                    domain.name,
                    f"Domain expiring in {calculate_time_remaining(domain.expiration_date)} days",
                    domain.expiration_date
                )
                
            # Update domain status
            domain.status = status['status']
            domain.last_check = datetime.utcnow()
        
        db.session.commit()
        
    except Exception as e:
        print(f"Error checking expiring domains: {e}")
