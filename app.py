"""
MailBlast Web App — Flask Backend
Gmail SMTP + App Password
Deployable on Render.com (free)
"""

import smtplib
import ssl
import base64
import os
import csv
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/ping')
def ping():
    return jsonify({'ok': True})


@app.route('/send', methods=['POST'])
def send_emails():
    try:
        # ── Parse form data ──
        gmail      = request.form.get('gmail', '').strip()
        password   = request.form.get('password', '').replace(' ', '')
        subject    = request.form.get('subject', '').strip()
        body       = request.form.get('body', '').strip()
        recipients_raw = request.form.get('recipients', '').strip()
        delay      = int(request.form.get('delay', 5))

        # ── Validate ──
        if not all([gmail, password, subject, body, recipients_raw]):
            return jsonify({'ok': False, 'error': 'All fields are required.'}), 400

        # ── Parse recipients ──
        recipients = []
        for line in recipients_raw.splitlines():
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2 and '@' in parts[-1]:
                recipients.append({
                    'company_name': parts[0],
                    'email': parts[-1]
                })

        if not recipients:
            return jsonify({'ok': False, 'error': 'No valid recipients found. Format: Company Name, email@example.com'}), 400

        # ── Load PDF if uploaded ──
        pdf_bytes = None
        pdf_name  = None
        if 'pdf' in request.files:
            f = request.files['pdf']
            if f and f.filename.endswith('.pdf'):
                pdf_bytes = f.read()
                pdf_name  = f.filename

        # ── Connect to Gmail ──
        context = ssl.create_default_context()
        results = []

        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(gmail, password)

            for i, r in enumerate(recipients):
                company = r['company_name']
                email   = r['email']
                try:
                    # Personalise
                    subj = subject.replace('{company_name}', company).replace('{name}', company)
                    bod  = body.replace('{company_name}', company).replace('{name}', company)

                    # Build message
                    msg = MIMEMultipart('mixed')
                    msg['From']    = gmail
                    msg['To']      = email
                    msg['Subject'] = subj

                    alt = MIMEMultipart('alternative')
                    alt.attach(MIMEText(bod, 'plain'))
                    html = f"""<html><body style="font-family:Arial,sans-serif;font-size:15px;
                    color:#202124;line-height:1.8;max-width:600px;margin:0 auto;padding:24px">
                    {''.join(f'<p style="margin:0 0 10px">{l}</p>' if l.strip() else '<br>'
                    for l in bod.split(chr(10)))}
                    </body></html>"""
                    alt.attach(MIMEText(html, 'html'))
                    msg.attach(alt)

                    # PDF attachment
                    if pdf_bytes and pdf_name:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(pdf_bytes)
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename="{pdf_name}"')
                        msg.attach(part)

                    server.sendmail(gmail, email, msg.as_string())
                    results.append({'company': company, 'email': email, 'status': 'sent'})

                except Exception as e:
                    results.append({'company': company, 'email': email, 'status': 'failed', 'error': str(e)})

                # Small delay between sends
                if i < len(recipients) - 1 and delay > 0:
                    import time
                    time.sleep(delay)

        sent   = sum(1 for r in results if r['status'] == 'sent')
        failed = sum(1 for r in results if r['status'] == 'failed')
        return jsonify({'ok': True, 'sent': sent, 'failed': failed, 'results': results})

    except smtplib.SMTPAuthenticationError:
        return jsonify({'ok': False, 'error': 'Gmail authentication failed. Check your email and App Password.'}), 401
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
