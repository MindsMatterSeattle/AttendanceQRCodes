import os
import csv
import io
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
port = os.environ.get("PORT")

# Ensure directories exist
os.makedirs('volunteers', exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def generate_qr_code(email):
    """Generate QR code for an email address"""
    try:
        # Generate QR code
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr.add_data(email)
        
        # Check if logo exists, if not generate without it
        logo_path = "logo.png" if os.path.exists("logo.png") else None

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
        
        filepath = f"volunteers/{email}.png"
        img.save(filepath)
        return filepath
    except Exception as e:
        print(f"Error generating QR code for {email}: {str(e)}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_qr_codes():
    emails = []
    
    # Get emails from manual input
    manual_emails = request.form.get('manual_emails', '').strip()
    if manual_emails:
        # Split by newlines and commas, clean up
        for email in manual_emails.replace(',', '\n').split('\n'):
            email = email.strip()
            if email and '@' in email:
                emails.append(email)
    
    # Get emails from uploaded CSV
    if 'csv_file' in request.files:
        file = request.files['csv_file']
        if file and file.filename and allowed_file(file.filename):
            try:
                file_content = file.read()
                csv_emails = extract_emails_from_csv(file_content)
                emails.extend(csv_emails)
            except Exception as e:
                flash(f'Error reading CSV file: {str(e)}')
                return redirect(url_for('index'))
    
    # Remove duplicates while preserving order
    unique_emails = []
    for email in emails:
        if email not in unique_emails:
            unique_emails.append(email)
    
    if not unique_emails:
        flash('No valid email addresses found. Please check your input.')
        return redirect(url_for('index'))
    
    # Generate QR codes
    generated_files = []
    failed_emails = []
    
    for email in unique_emails:
        filepath = generate_qr_code(email)
        if filepath:
            generated_files.append((email, filepath))
        else:
            failed_emails.append(email)
    
    if failed_emails:
        flash(f'Failed to generate QR codes for: {", ".join(failed_emails)}')
    
    if generated_files:
        flash(f'Successfully generated {len(generated_files)} QR codes!')
        return render_template('results.html', 
                             generated_files=generated_files, 
                             failed_emails=failed_emails)
    else:
        flash('No QR codes were generated successfully.')
        return redirect(url_for('index'))

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
    
    