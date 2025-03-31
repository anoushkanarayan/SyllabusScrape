"""
main.py - Main entry point for the Syllabus Calendar Generator
"""
import os
import logging
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template

# Import our configuration
import config

# Import our modules
from pdf_extractor import PDFExtractor
from date_extractor import DateExtractor, SyllabusEventExtractor
from calendar_integration import GoogleCalendarIntegration, AppleCalendarIntegration, detect_event_duration
from syllabus_processors import get_syllabus_processor

# Set up logging
logger = config.setup_logging()

# Initialize Flask app
app = Flask(__name__, 
            static_folder='static', 
            template_folder='templates')

# Configure app from our config file
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = config.ALLOWED_EXTENSIONS
app.config['DEBUG'] = config.DEBUG

# Initialize modules
pdf_extractor = PDFExtractor()
google_calendar = GoogleCalendarIntegration(
    credentials_path=config.GOOGLE_CREDENTIALS_PATH,
    token_path=config.GOOGLE_TOKEN_PATH
)
apple_calendar = AppleCalendarIntegration()

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "version": config.APP_VERSION,
        "timestamp": datetime.now().isoformat()
    })

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
        # Get parameters from request
        course_name = request.form.get('course_name', None)
        year_str = request.form.get('year', None)
        
        # Process year parameter
        year = None
        if year_str and year_str.isdigit():
            year = int(year_str)
        else:
            # Use current year as default
            year = datetime.now().year
        
        # Create a temporary file
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'syllabus.pdf')
        file.save(temp_path)
        
        # Extract text from PDF
        with open(temp_path, 'rb') as pdf_file:
            extracted_text = pdf_extractor.extract_text(pdf_file)
        
        # Use the appropriate syllabus processor
        processor = get_syllabus_processor(extracted_text, year=year)
        events = processor.process()
        
        # If the processor couldn't extract events, fall back to the generic extractor
        if not events:
            logger.info("Using fallback event extractor")
            with open(temp_path, 'rb') as pdf_file:
                syllabus_extractor = SyllabusEventExtractor(year=year)
                events = syllabus_extractor.process_syllabus(pdf_file, course_name=course_name)
        
        # Prepare events for JSON serialization
        serializable_events = []
        for event in events:
            # Add course name if not already present
            if 'course' not in event and course_name:
                event['course'] = course_name
                
            # Convert datetime objects to strings for JSON serialization
            if 'date' in event:
                event['date_str'] = event['date'].strftime('%Y-%m-%d %H:%M:%S')
                
            # Detect event duration
            event['duration_minutes'] = detect_event_duration(event)
            
            # Create a serializable copy
            serializable_event = event.copy()
            if 'date' in serializable_event:
                del serializable_event['date']
                
            serializable_events.append(serializable_event)
        
        # Clean up
        os.remove(temp_path)
        os.rmdir(temp_dir)
        
        return jsonify({
            "success": True,
            "events": serializable_events,
            "count": len(serializable_events)
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
                try:
                    event['date'] = datetime.strptime(event['date_str'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return jsonify({"error": f"Invalid date format: {event['date_str']}"}), 400
        
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
                try:
                    event['date'] = datetime.strptime(event['date_str'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return jsonify({"error": f"Invalid date format: {event['date_str']}"}), 400
        
        # Generate ICS file
        temp_dir = tempfile.mkdtemp()
        ics_path = os.path.join(temp_dir, 'syllabus_events.ics')
        apple_calendar.generate_ics_file(events_data, filename=ics_path)
        
        if not os.path.exists(ics_path):
            return jsonify({"error": "Failed to generate ICS file"}), 500
            
        return send_file(
            ics_path,
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
        # Create a temporary file
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'syllabus.pdf')
        file.save(temp_path)
        
        # Extract text from PDF
        with open(temp_path, 'rb') as pdf_file:
            text = pdf_extractor.extract_text(pdf_file)
        
        # Clean up
        os.remove(temp_path)
        os.rmdir(temp_dir)
        
        return jsonify({
            "success": True,
            "text": text
        })
        
    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Check for Google API credentials
    if not os.path.exists(config.GOOGLE_CREDENTIALS_PATH):
        logger.warning(f"Google API credentials file not found at {config.GOOGLE_CREDENTIALS_PATH}.")
        logger.warning("Google Calendar integration will not work.")
    
    # Ensure upload folder exists
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    
    # Start the application
    logger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION}")
    app.run(debug=config.DEBUG, host=config.API_HOST, port=config.API_PORT)