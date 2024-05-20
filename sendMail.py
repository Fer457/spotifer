import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

SMTP_HOST = ''
SMTP_PORT = 587
SMTP_USERNAME = ''
SMTP_PASSWORD = ''
EMAIL_FROM = ''
EMAIL_TO = ''
EMAIL_SUBJECT = 'Tu resumen de spotifer de hoy'

def send_email_with_summary(subject, body, images):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject

    email_body = body
    for image_path in images:
        with open(image_path, 'rb') as img_file:
            img_data = img_file.read()
            img_data_base64 = base64.b64encode(img_data).decode('utf-8')

    msg.attach(MIMEText(email_body, 'html'))

    server = smtplib.SMTP(host=SMTP_HOST, port=SMTP_PORT)
    server.starttls()
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    server.send_message(msg)
    server.quit()

    print(f'Correo enviado a {EMAIL_TO} con el resumen del día.')