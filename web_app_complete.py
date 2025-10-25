# web_app_complete.py
import os
import cv2
import numpy as np
from flask import Flask, render_template, request, send_file, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import secrets
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Production settings
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

# Usage tracking
USAGE_FILE = 'usage_stats.json'

def load_usage_stats():
    try:
        with open(USAGE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'total_files': 0, 'daily_files': {}, 'user_sessions': 0}

def save_usage_stats(stats):
    with open(USAGE_FILE, 'w') as f:
        json.dump(stats, f)

def track_usage():
    stats = load_usage_stats()
    stats['total_files'] += 1
    today = datetime.now().strftime('%Y-%m-%d')
    stats['daily_files'][today] = stats['daily_files'].get(today, 0) + 1
    save_usage_stats(stats)

def allowed_file(filename):
    allowed_extensions = {'mp4', 'avi', 'mov', 'mkv', 'jpg', 'jpeg', 'png', 'bmp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def remove_watermark(input_path, output_path):
    """Enhanced watermark removal"""
    try:
        if input_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
            # Image processing
            img = cv2.imread(input_path)
            if img is None:
                return False, "Failed to read image"
            
            # Remove red watermarks (common in videos)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Define red color range
            lower_red1 = np.array([0, 120, 70])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 120, 70])
            upper_red2 = np.array([180, 255, 255])
            
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            mask = mask1 + mask2
            
            # Inpaint the masked areas
            result = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
            cv2.imwrite(output_path, result)
            return True, "Watermark removed successfully from image"
            
        else:
            # Video processing
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                return False, "Failed to open video"
            
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process each frame
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                lower_red1 = np.array([0, 120, 70])
                upper_red1 = np.array([10, 255, 255])
                lower_red2 = np.array([170, 120, 70])
                upper_red2 = np.array([180, 255, 255])
                
                mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                mask = mask1 + mask2
                
                processed_frame = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
                out.write(processed_frame)
                frame_count += 1
            
            cap.release()
            out.release()
            return True, f"Video processed successfully - {frame_count} frames processed"
            
    except Exception as e:
        return False, f"Processing error: {str(e)}"

# Contact form functions
def send_contact_email(name, email, message):
    """Send contact form email - currently prints to console"""
    print(f"Contact Form Submission:")
    print(f"Name: {name}")
    print(f"Email: {email}")
    print(f"Message: {message}")
    return True

# Routes for all pages
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            message = request.form.get('message', '').strip()
            
            # Basic validation
            if not all([name, email, message]):
                return render_template('contact.html', error='All fields are required')
            
            # Send email (currently prints to console)
            send_contact_email(name, email, message)
            
            return render_template('contact.html', success='Message sent successfully! We will respond within 24 hours.')
            
        except Exception as e:
            return render_template('contact.html', error='Failed to send message. Please try again.')
    
    return render_template('contact.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'File type not allowed. Supported: MP4, AVI, MOV, MKV, JPG, PNG, BMP'})
    
    try:
        # Track usage
        track_usage()
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)
        
        # Generate output filename
        name, ext = os.path.splitext(filename)
        output_filename = f"{name}_processed{ext}"
        output_path = os.path.join(app.config['PROCESSED_FOLDER'], output_filename)
        
        # Process the file
        success, message = remove_watermark(input_path, output_path)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'download_url': f'/download/{output_filename}'
            })
        else:
            # Clean up on failure
            if os.path.exists(input_path):
                os.remove(input_path)
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['PROCESSED_FOLDER'], secure_filename(filename))
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return "File not found", 404
    except Exception as e:
        return f"Download error: {str(e)}", 500

@app.route('/stats')
def stats():
    stats = load_usage_stats()
    return jsonify(stats)

# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'message': 'File too large. Maximum size is 100MB'}), 413

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Page not found'}), 404

if __name__ == '__main__':
    print("🚀 Watermark Remover Pro - Complete Version")
    print("📧 Access at: http://localhost:5000")
    print("📊 Features: Beautiful UI, FAQ, Contact, Disclaimer, Privacy Policy, Terms")
    print("⚡ Enhanced watermark removal algorithm")
    app.run(host='0.0.0.0', port=5000, debug=True)