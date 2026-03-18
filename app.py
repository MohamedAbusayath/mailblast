"""
MailBlast Web App — Flask Backend
Uses Gmail API via HTTP (no SMTP) — works on Render free tier
"""
import os
import base64
import traceback
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import urllib.request
import urllib.parse
import urllib.error
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ping')
def ping():
    return jsonify({'ok': True})

def get_access_token(refresh_token, client_id, client_secret):
    """Exchange refresh token for access token via HTTPS."""
    data = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
    }).encode()
    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=data,
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())['access_token']

def send_via_gmail_api(access_token, sender, to_email, subject, body, pdf_bytes=None, pdf_name=None):
    """Send email using Gmail REST API over HTTPS."""
    msg = MIMEMultipart('mixed')
    msg['From']    = sender
    msg['To']      = to_email
    msg['Subject'] = subject

    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(body, 'plain'))
    html_body = "<html><body style='font-family:Arial,sans-serif;font-size:15px;color:#202124;line-height:1.8;max-width:600px;margin:0 auto;padding:24px'>"
    for line in body.split('\n'):
        html_body += f"<p style='margin:0 0 10px'>{line}</p>" if line.strip() else "<br>"
    html_body += "</body></html>"
    alt.attach(MIMEText(html_body, 'html'))
    msg.attach(alt)

    if pdf_bytes and pdf_name:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{pdf_name}"')
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    payload = json.dumps({'raw': raw}).encode()
    req = urllib.request.Request(
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        data=payload,
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())

@app.route('/send', methods=['POST'])
def send_one():
    try:
        client_id     = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()
        refresh_token = request.form.get('refresh_token', '').strip()
        sender        = request.form.get('sender', '').strip()
        subject       = request.form.get('subject', '').strip()
        body          = request.form.get('body', '').strip()
        to_email      = request.form.get('to_email', '').strip()
        company       = request.form.get('company', '').strip()

        print(f"[SEND] to={to_email} from={sender}")

        if not all([client_id, client_secret, refresh_token, sender, to_email, subject, body]):
            return jsonify({'ok': False, 'error': 'Missing required fields.'}), 400

        # Personalise
        subj = subject.replace('{company_name}', company).replace('{name}', company)
        bod  = body.replace('{company_name}', company).replace('{name}', company)

        # PDF
        pdf_bytes = None
        pdf_name  = None
        if 'pdf' in request.files:
            f = request.files['pdf']
            if f and f.filename and f.filename.endswith('.pdf'):
                pdf_bytes = f.read()
                pdf_name  = f.filename

        # Get access token
        access_token = get_access_token(refresh_token, client_id, client_secret)

        # Send via Gmail API
        send_via_gmail_api(access_token, sender, to_email, subj, bod, pdf_bytes, pdf_name)

        print(f"[OK] Sent to {to_email}")
        return jsonify({'ok': True})

    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"[HTTP ERROR] {e.code}: {err_body}")
        if e.code == 401:
            return jsonify({'ok': False, 'error': 'Authentication failed. Check your OAuth credentials.'}), 401
        return jsonify({'ok': False, 'error': f'Gmail API error {e.code}: {err_body[:200]}'}), 500

    except Exception as e:
        print(f"[ERROR] {traceback.format_exc()}")
        return jsonify({'ok': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)