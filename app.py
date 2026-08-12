import os
import csv
import io
import json
import re
import sys
import uuid
from datetime import datetime
from flask import Flask, request, render_template, flash, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import VerticalGradiantColorMask
import zipfile
import tempfile

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
MAX_MANUAL_EMAILS = 50
TASKS_DIR = 'task_queue'

os.makedirs('volunteers', exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(TASKS_DIR, exist_ok=True)
port = os.environ.get("PORT")

def generate_qr_code(email):
    """Generate QR code for an email address"""
    try:
        # Generate QR code
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr.add_data(email)
        
        # Check if logo exists, if not generate without it
        logo_path = "logo.png" if os.path.exists("logo.png") else None
        try:
            if logo_path:
                img = qr.make_image(
                    image_factory=StyledPilImage, 
                    color_mask=VerticalGradiantColorMask(
                        bottom_color=(0, 0, 0), 
                        top_color=(0, 56, 150)
                    ), 
                    embeded_image_path=logo_path
                )
            else:
                img = qr.make_image(
                    image_factory=StyledPilImage, 
                    color_mask=VerticalGradiantColorMask(
                        bottom_color=(0, 0, 0), 
                        top_color=(0, 56, 150)
                    )
                )
        except Exception as e:
            print(f'Error generating QR code for {email}: {e}')
            return None
        
        filepath = f"volunteers/{email}.png"
        img.save(filepath)
        try:
            img.close()
        except Exception:
            pass
        return filepath
    except Exception as e:
        print(f"Error generating QR code for {email}: {str(e)}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

def task_file_path(task_id):
    return os.path.join(TASKS_DIR, f"{task_id}.json")

def save_task(task):
    with open(task_file_path(task['id']), 'w', encoding='utf-8') as f:
        json.dump(task, f, indent=2)

def load_task(task_id):
    path = task_file_path(task_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def enqueue_task(emails):
    task_id = uuid.uuid4().hex
    task = {
        'id': task_id,
        'status': 'queued',
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'updated_at': datetime.utcnow().isoformat() + 'Z',
        'email_count': len(emails),
        'emails': emails,
        'generated_files': [],
        'failed_emails': [],
    }
    save_task(task)
    return task_id

def extract_emails_from_csv(file_content):
    """Extract email addresses from CSV content"""
    emails = []
    try:
        # Try to decode the file content
        content = file_content.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        
        for _, row in enumerate(reader):
            for cell in row:
                # Simple email validation
                if '@' in cell and '.' in cell:
                    email = cell.strip()
                    if email and email not in emails:
                        emails.append(email)
    except Exception as e:
        print(f"Error reading CSV: {str(e)}")
    
    return emails

def parse_manual_emails(text):
    for token in re.split(r'[\s,;]+', text):
        email = token.strip()
        if email and '@' in email and '.' in email:
            yield email

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_qr_codes():
    unique_emails = []
    seen = set()

    manual_emails = request.form.get('manual_emails', '').strip()
    if manual_emails:
        for email in parse_manual_emails(manual_emails):
            if email not in seen:
                seen.add(email)
                unique_emails.append(email)

    # Get emails from uploaded CSV
    if 'csv_file' in request.files:
        file = request.files['csv_file']
        if file and file.filename and allowed_file(file.filename):
            try:
                file_content = file.read()
                csv_emails = extract_emails_from_csv(file_content)
                unique_emails.extend(csv_emails)
            except Exception as e:
                flash(f'Error reading CSV file: {str(e)}')
                return redirect(url_for('index'))
    
    # Remove duplicates while preserving order
    final_emails = []
    for email in unique_emails:
        if email not in final_emails:
            final_emails.append(email)
    
    if not final_emails:
        flash('No valid email addresses found. Please check your input.')
        return redirect(url_for('index'))

    if len(final_emails) > MAX_MANUAL_EMAILS:
        flash(f'Manual entry is limited to {MAX_MANUAL_EMAILS} unique email addresses. Please use CSV upload for larger batches.')
        return redirect(url_for('index'))

    task_id = enqueue_task(final_emails)
    flash(f'Your request has been queued for background processing. Task ID: {task_id}')
    return render_template('queued.html', task_id=task_id, email_count=len(final_emails))

@app.route('/task/<task_id>')
def task_status(task_id):
    task = load_task(task_id)
    if not task:
        flash('Task not found.')
        return redirect(url_for('index'))

    return render_template('task_status.html', task=task)

@app.route('/download_all')
def download_all():
    """Create a zip file with all generated QR codes"""
    try:
        # Create a temporary zip file
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        with zipfile.ZipFile(temp_zip.name, 'w') as zip_file:
            volunteers_dir = 'volunteers'
            if os.path.exists(volunteers_dir):
                for filename in os.listdir(volunteers_dir):
                    if filename.endswith('.png'):
                        file_path = os.path.join(volunteers_dir, filename)
                        zip_file.write(file_path, filename)
        clear_files()
        return send_file(temp_zip.name, 
                        as_attachment=True, 
                        download_name='qr_codes.zip',
                        mimetype='application/zip')
    except Exception as e:
        flash(f'Error creating zip file: {str(e)}')
        return redirect(url_for('index'))

@app.route('/volunteers/<filename>')
def serve_qr_code(filename):
    """Serve QR code images"""
    return send_from_directory('volunteers', filename)

@app.route('/clear')
def clear_files():
    """Clear all generated QR codes"""
    try:
        volunteers_dir = 'volunteers'
        if os.path.exists(volunteers_dir):
            for filename in os.listdir(volunteers_dir):
                if filename.endswith('.png'):
                    os.remove(os.path.join(volunteers_dir, filename))
        flash('All QR codes have been cleared.')
    except Exception as e:
        flash(f'Error clearing files: {str(e)}')
    
    return redirect(url_for('index'))

def run():
    app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=port)

