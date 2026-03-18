"""
MailBlast Web App — Flask Backend
Gmail SMTP + App Password | One email per request
"""
import smtplib
import ssl
import os
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ping')
def ping():
    return jsonify({'ok': True})

@app.route('/send', methods=['POST'])
def send_one():
    try:
        gmail    = request.form.get('gmail', '').strip()
        password = request.form.get('password', '').replace(' ', '')
        subject  = request.form.get('subject', '').strip()
        body     = request.form.get('body', '').strip()
        to_email = request.form.get('to_email', '').strip()
        company  = request.form.get('company', '').strip()

        print(f"[SEND] to={to_email} from={gmail}")

        if not all([gmail, password, to_email, subject, body]):
            return jsonify({'ok': False, 'error': 'Missing required fields.'}), 400

        # Personalise
        subj = subject.replace('{company_name}', company).replace('{name}', company)
        bod  = body.replace('{company_name}', company).replace('{name}', company)

        # Build email
        msg = MIMEMultipart('mixed')
        msg['From']    = gmail
        msg['To']      = to_email
        msg['Subject'] = subj

        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(bod, 'plain'))
        html_body = "<html><body style='font-family:Arial,sans-serif;font-size:15px;color:#202124;line-height:1.8;max-width:600px;margin:0 auto;padding:24px'>"
        for line in bod.split('\n'):
            html_body += f"<p style='margin:0 0 10px'>{line}</p>" if line.strip() else "<br>"
        html_body += "</body></html>"
        alt.attach(MIMEText(html_body, 'html'))
        msg.attach(alt)

        # PDF attachment
        if 'pdf' in request.files:
            f = request.files['pdf']
            if f and f.filename and f.filename.endswith('.pdf'):
                pdf_bytes = f.read()
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(pdf_bytes)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{f.filename}"')
                msg.attach(part)

        # Send via Gmail SMTP — timeout=25 keeps it under Render's 30s limit
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context, timeout=25) as server:
            server.login(gmail, password)
            server.sendmail(gmail, to_email, msg.as_string())

        print(f"[OK] Sent to {to_email}")
        return jsonify({'ok': True})

    except smtplib.SMTPAuthenticationError:
        error = 'Gmail authentication failed. Check your App Password — make sure 2-Step Verification is ON.'
        print(f"[AUTH ERROR]")
        return jsonify({'ok': False, 'error': error}), 401

    except smtplib.SMTPRecipientsRefused:
        error = f'Email address rejected: {to_email}'
        print(f"[RECIPIENT ERROR]")
        return jsonify({'ok': False, 'error': error}), 400

    except smtplib.SMTPConnectError:
        error = 'Could not connect to Gmail SMTP. Please try again in a few seconds.'
        print(f"[CONNECT ERROR]")
        return jsonify({'ok': False, 'error': error}), 500

    except TimeoutError:
        error = 'Connection timed out. Please try again.'
        print(f"[TIMEOUT ERROR]")
        return jsonify({'ok': False, 'error': error}), 500

    except smtplib.SMTPException as e:
        print(f"[SMTP ERROR] {e}")
        return jsonify({'ok': False, 'error': f'SMTP error: {str(e)}'}), 500

    except Exception as e:
        print(f"[ERROR] {traceback.format_exc()}")
        return jsonify({'ok': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)