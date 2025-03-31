"""
app.py - Flask API for Syllabus Calendar Generator
"""
import os
import logging
import tempfile
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Import our modules
from pdf_extractor import PDFExtractor
from date_extractor import DateExtractor, SyllabusEventExtractor
from calendar_integration import GoogleCalendarIntegration, AppleCalendarIntegration, detect_event_duration

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Initialize modules
pdf_extractor = PDFExtractor()
google_calendar = GoogleCalendarIntegration()
apple_calendar = AppleCalendarIntegration()

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"})

@app.route('/api/upload', methods=['POST'])
def upload_syllabus():
    """
    Endpoint to upload a syllabus and extract events.
    
    Returns JSON with extracted events.
    """
    # Check if a file was uploaded
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400
    
    try:
        # Save the file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Get course name from request (optional)
        course_name = request.form.get('course_name', None)
        year = request.form.get('year', None)
        
        if year and year.isdigit():
            year = int(year)
        else:
            # Use current year as default
            from datetime import datetime
            year = datetime.now().year
        
        # Process the syllabus
        with open(filepath, 'rb') as pdf_file:
            # Create event extractor with the provided year
            syllabus_extractor = SyllabusEventExtractor(year=year)
            events = syllabus_extractor.process_syllabus(pdf_file, course_name=course_name)
            
            # Add processing metadata
            for event in events:
                # Convert datetime objects to strings for JSON serialization
                event['date_str'] = event['date'].strftime('%Y-%m-%d %H:%M:%S')
                
                # Detect event duration
                event['duration_minutes'] = detect_event_duration(event)
                
                # Clean up non-serializable objects for JSON
                if 'date' in event:
                    del event['date']
        
        # Clean up
        os.remove(filepath)
        
        return jsonify({
            "success": True,
            "events": events,
            "count": len(events)
        })
        
    except Exception as e:
        logger.error(f"Error processing syllabus: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/calendars/google', methods=['GET'])
def list_google_calendars():
    """
    Endpoint to list available Google calendars.
    
    Requires authentication first.
    """
    try:
        if not google_calendar.authenticate():
            return jsonify({"error": "Google Calendar authentication failed"}), 401
            
        calendars = google_calendar.list_calendars()
        return jsonify({
            "success": True,
            "calendars": calendars
        })
        
    except Exception as e:
        logger.error(f"Error listing Google calendars: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/events/google', methods=['POST'])
def create_google_events():
    """
    Endpoint to create events in Google Calendar.
    
    Expects JSON with events data and calendar_id.
    """
    try:
        data = request.json
        
        if not data or 'events' not in data or 'calendar_id' not in data:
            return jsonify({"error": "Missing required data"}), 400
            
        events_data = data['events']
        calendar_id = data['calendar_id']
        
        # Convert string dates back to datetime objects
        for event in events_data:
            if 'date_str' in event:
                from datetime import datetime
                event['date'] = datetime.strptime(event['date_str'], '%Y-%m-%d %H:%M:%S')
        
        if not google_calendar.authenticate():
            return jsonify({"error": "Google Calendar authentication failed"}), 401
            
        created_events = google_calendar.create_events_batch(calendar_id, events_data)
        
        return jsonify({
            "success": True,
            "created_events": len(created_events)
        })
        
    except Exception as e:
        logger.error(f"Error creating Google calendar events: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/events/apple', methods=['POST'])
def create_apple_events():
    """
    Endpoint to generate an ICS file for Apple Calendar.
    
    Expects JSON with events data.
    """
    try:
        data = request.json
        
        if not data or 'events' not in data:
            return jsonify({"error": "Missing required data"}), 400
            
        events_data = data['events']
        
        # Convert string dates back to datetime objects
        for event in events_data:
            if 'date_str' in event:
                from datetime import datetime
                event['date'] = datetime.strptime(event['date_str'], '%Y-%m-%d %H:%M:%S')
        
        # Generate ICS file
        ics_file = apple_calendar.generate_ics_file(events_data)
        
        if not ics_file:
            return jsonify({"error": "Failed to generate ICS file"}), 500
            
        return send_file(
            ics_file,
            as_attachment=True,
            download_name="syllabus_events.ics",
            mimetype="text/calendar"
        )
        
    except Exception as e:
        logger.error(f"Error generating ICS file: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/extract-text', methods=['POST'])
def extract_text():
    """
    Endpoint to extract text from a syllabus without processing dates.
    
    Useful for debugging and testing.
    """
    # Check if a file was uploaded
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400
    
    try:
        # Save the file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Extract text from PDF
        with open(filepath, 'rb') as pdf_file:
            text = pdf_extractor.extract_text(pdf_file)
        
        # Clean up
        os.remove(filepath)
        
        return jsonify({
            "success": True,
            "text": text
        })
        
    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Make sure credentials file exists for Google Calendar
    if not os.path.exists('credentials.json'):
        logger.warning("Google API credentials.json file not found. Google Calendar integration will not work.")
    
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))