import whois
from datetime import datetime, timedelta
from flask_mail import Message
from app import mail
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

        if 'pendingdelete' in status_text:
            status = 'PendingDelete'
            time_info = format_availability_date(abs(days_remaining) + 5 if days_remaining else None)  # Typical grace period
        else:
            status = 'Active' if days_remaining and days_remaining > 0 else 'Expired'
            time_info = format_time_status(days_remaining)

        # Construct detailed status information
        detailed_info = {
            'registrar': w.registrar,
            'whois_server': w.whois_server,
            'name_servers': w.name_servers if isinstance(w.name_servers, list) else [w.name_servers] if w.name_servers else [],
            'dnssec': getattr(w, 'dnssec', 'Unknown'),
            'status_codes': w.status if isinstance(w.status, list) else [w.status] if w.status else []
        }

        return {
            'status': status,
            'registration_date': registration_date,
            'expiration_date': expiration_date,
            'time_info': time_info,
            'detailed_info': detailed_info,
            'raw_response': str(w)
        }
    except Exception as e:
        return {
            'status': 'Error',
            'registration_date': None,
            'expiration_date': None,
            'time_info': 'Unable to check',
            'detailed_info': {'error': str(e)},
            'raw_response': str(e)
        }

def send_notification_email(user_email, domain_name, status_change):
    msg = Message(
        'Domain Status Change Notification',
        sender='noreply@domaintracker.com',
        recipients=[user_email]
    )
    msg.body = f"""
    Domain Status Change Alert
    
    Domain: {domain_name}
    New Status: {status_change}
    Time: {datetime.utcnow()}
    """
    mail.send(msg)
