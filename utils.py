import whois
from datetime import datetime
from flask_mail import Message
from app import mail
import socket

def check_domain_status(domain_name):
    try:
        w = whois.whois(domain_name)
        status = {
            'status': 'Active',
            'registration_date': w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date,
            'expiration_date': w.expiration_date[0] if isinstance(w.expiration_date, list) else w.expiration_date
        }
    except Exception as e:
        status = {
            'status': 'Error',
            'registration_date': None,
            'expiration_date': None
        }
    return status

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
