from flask_mail import Message, Mail
from typing import List
import smtplib


class EmailService:
    def __init__(self, app):
        self.mail = Mail(app)

    def send_email(self, sender: str, recipients: List[str], subject: str, body: str):
        with self.mail.connect() as conn:
            message = Message(subject, sender=sender, recipients=recipients)
            message.body = body
            conn.send(message)

