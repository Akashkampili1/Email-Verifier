from flask import Flask, request, jsonify, render_template, send_file
import smtplib
import dns.resolver
from email_validator import validate_email, EmailNotValidError
import pandas as pd
import io

app = Flask(__name__)

generated_emails = []  # Global variable to store generated emails

def get_mx_records(domain):
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_records = [record.exchange.to_text() for record in records]
        return mx_records
    except dns.resolver.NoAnswer:
        print(f"No MX records found for the domain: {domain}")
        return []
    except dns.resolver.NXDOMAIN:
        print(f"Domain does not exist: {domain}")
        return []
    except Exception as e:
        print(f"Error fetching MX records: {e}")
        return []

def verify_email(email):
    try:
        # Validate the email format
        valid = validate_email(email)
        email = valid.email
        
        domain = email.split('@')[1]
        mx_records = get_mx_records(domain)
        
        if not mx_records:
            return False
        
        # Connect to the first mail server
        mx_host = mx_records[0]
        
        server = smtplib.SMTP(mx_host, timeout=10)
        server.set_debuglevel(0)
        
        # SMTP conversation
        server.helo(server.local_hostname)
        server.mail('test@example.com')
        code, message = server.rcpt(email)
        server.quit()
        
        # Check if the email exists based on the SMTP response
        return code == 250
    except EmailNotValidError as e:
        print(f"Invalid email: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"SMTP connection error: {e}")
        return False
    except smtplib.SMTPServerDisconnected as e:
        print(f"SMTP server disconnected: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"SMTP error: {e}")
        return False
    except Exception as e:
        print(f"Error verifying email: {e}")
        return False

def enumerate_emails(start_usn, end_usn, domain):
    try:
        start_number = int(start_usn[-3:])
        end_number = int(end_usn[-3:])
        prefix = start_usn[:-3]

        if start_number > end_number:
            raise ValueError("Start USN should be less than or equal to End USN")

        emails = [f"{prefix}{str(i).zfill(3)}@{domain}" for i in range(start_number, end_number + 1)]
        return emails
    except Exception as e:
        print(f"Error enumerating emails: {e}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    if verify_email(email):
        return jsonify({'status': 'valid'})
    else:
        return jsonify({'status': 'invalid'})

@app.route('/enumerate', methods=['GET', 'POST'])
def enumerate():
    global generated_emails
    if request.method == 'GET':
        return render_template('enumerate.html')
    elif request.method == 'POST':
        data = request.get_json()
        usn_start = data.get('usn_start')
        usn_end = data.get('usn_end')
        domain = data.get('domain')
        if not usn_start or not usn_end or not domain:
            return jsonify({'error': 'USN start, end, and domain are required'}), 400

        generated_emails = enumerate_emails(usn_start, usn_end, domain)
        return jsonify({'emails': generated_emails})

@app.route('/download_emails')
def download_emails():
    global generated_emails
    if not generated_emails:
        return jsonify({'error': 'No emails generated yet'}), 400

    # Create a DataFrame and convert it to CSV
    df = pd.DataFrame(generated_emails, columns=['Email'])
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    # Send the CSV file as a response
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='emails.csv')

if __name__ == '__main__':
    app.run(debug=True)
