"""
calendar_integration.py - Module for integrating with calendar systems
"""
import os
import datetime
import logging
import re
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Google Calendar API settings
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarIntegration:
    """Class to handle integration with Google Calendar."""
    
    EVENT_COLORS = {
        'exam': '11',      # Red
        'quiz': '5',       # Yellow
        'homework': '9',   # Blue
        'project': '10',   # Green
        'lab': '6',        # Orange
        'deadline': '8',   # Gray
        'schedule': '7'    # Purple
    }
    
    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        """
        Initialize the Google Calendar integration.
        
        Args:
            credentials_path (str): Path to the credentials.json file
            token_path (str): Path to save the token.json file
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.service = None
    
    def authenticate(self):
        """
        Authenticate with Google Calendar API.
        
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        try:
            # Check if token already exists
            if os.path.exists(self.token_path):
                try:
                    with open(self.token_path, 'r') as token_file:
                        token_json = token_file.read()
                        self.creds = Credentials.from_authorized_user_info(
                            info=json.loads(token_json),
                            scopes=SCOPES
                        )
                except Exception as e:
                    logger.error(f"Error reading token file: {str(e)}")
                    # If token file is corrupted, remove it and proceed with new auth
                    os.remove(self.token_path)
                    self.creds = None
            else:
                self.creds = None
            
            # If there are no (valid) credentials available, let the user log in
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES)
                    self.creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                with open(self.token_path, 'w') as token:
                    token.write(self.creds.to_json())
            
            # Build the service
            self.service = build('calendar', 'v3', credentials=self.creds)
            return True
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    def list_calendars(self):
        """
        List available calendars.
        
        Returns:
            list: A list of calendar dictionaries
        """
        if not self.service:
            if not self.authenticate():
                return []
        
        try:
            calendar_list = self.service.calendarList().list().execute()
            return calendar_list.get('items', [])
            
        except HttpError as e:
            logger.error(f"Error listing calendars: {str(e)}")
            return []
    
    def create_event(self, calendar_id, event_data):
        """
        Create an event in Google Calendar.
        
        Args:
            calendar_id (str): The ID of the calendar to create the event in
            event_data (dict): The event data dictionary from the extractor
            
        Returns:
            dict or None: The created event, or None if creation failed
        """
        if not self.service:
            if not self.authenticate():
                return None
        
        try:
            # Prepare the event
            event = {
                'summary': event_data['title'],
                'description': f"Event extracted from syllabus\nOriginal text: {event_data['original_text']}\nContext: {event_data['context']}",
                'start': {
                    'dateTime': event_data['date'].isoformat(),
                    'timeZone': 'America/Los_Angeles',  # Default timezone, should be configurable
                },
                'end': {
                    'dateTime': (event_data['date'] + datetime.timedelta(hours=1)).isoformat(),  # Default 1 hour duration
                    'timeZone': 'America/Los_Angeles',
                },
                'colorId': self.EVENT_COLORS.get(
                    event_data['event_type'], 
                    '1'  # Default color (blue)
                ),
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60}        # 1 hour before
                    ]
                }
            }
            
            # Add course name if available
            if 'course' in event_data:
                event['summary'] = f"[{event_data['course']}] {event['summary']}"
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            logger.info(f"Event created: {created_event.get('htmlLink')}")
            return created_event
            
        except HttpError as e:
            logger.error(f"Error creating event: {str(e)}")
            return None
    
    def create_events_batch(self, calendar_id, events_data):
        """
        Create multiple events in Google Calendar.
        
        Args:
            calendar_id (str): The ID of the calendar to create the events in
            events_data (list): A list of event data dictionaries
            
        Returns:
            list: A list of created events
        """
        created_events = []
        
        for event_data in events_data:
            created_event = self.create_event(calendar_id, event_data)
            if created_event:
                created_events.append(created_event)
        
        return created_events


class AppleCalendarIntegration:
    """
    Placeholder for Apple Calendar integration.
    
    Note: Direct integration with Apple Calendar requires iOS/macOS native code.
    For a web application, we'd typically provide an .ics file for users to import.
    """
    
    def __init__(self):
        """Initialize the Apple Calendar integration."""
        pass
    
    def generate_ics_file(self, events_data, filename='syllabus_events.ics'):
        """
        Generate an .ics file for Apple Calendar import.
        
        Args:
            events_data (list): A list of event data dictionaries
            filename (str): The name of the .ics file to generate
            
        Returns:
            str: The path to the generated .ics file
        """
        try:
            from ics import Calendar, Event
            
            calendar = Calendar()
            
            for event_data in events_data:
                event = Event()
                event.name = event_data['title']
                event.begin = event_data['date']
                event.end = event_data['date'] + datetime.timedelta(hours=1)  # Default 1 hour duration
                event.description = f"Event extracted from syllabus\nOriginal text: {event_data['original_text']}\nContext: {event_data['context']}"
                
                # Add course name if available
                if 'course' in event_data:
                    event.name = f"[{event_data['course']}] {event.name}"
                
                calendar.events.add(event)
            
            with open(filename, 'w') as f:
                f.write(str(calendar))
            
            return filename
            
        except ImportError:
            logger.error("ics package not installed. Install with 'pip install ics'")
            return None
            
    def create_calendar_event(self, event_data):
        """
        Create an event in Apple Calendar (placeholder for native integration).
        
        In a real implementation, this would use macOS/iOS native APIs.
        For a web app, we'd typically direct users to import the .ics file.
        
        Args:
            event_data (dict): The event data dictionary
            
        Returns:
            bool: Always returns False as this is a placeholder
        """
        logger.warning("Direct Apple Calendar integration requires native iOS/macOS code.")
        return False


# Helper function to detect event duration based on context
def detect_event_duration(event_data):
    """
    Attempt to detect the duration of an event based on its description and type.
    
    Args:
        event_data (dict): The event data dictionary
        
    Returns:
        int: The duration in minutes
    """
    # Default durations by event type
    default_durations = {
        'exam': 120,       # 2 hours
        'quiz': 60,        # 1 hour
        'homework': 0,     # 0 = no duration (just a due date)
        'project': 0,      # 0 = no duration (just a due date)
        'lab': 120,        # 2 hours
        'deadline': 0,     # 0 = no duration (just a due date)
        'schedule': 60     # 1 hour
    }
    
    # Try to detect duration from context
    context = event_data.get('context', '').lower()
    
    # Look for time ranges like "2-4pm" or "9:30-10:45"
    time_range_match = re.search(r'(\d{1,2}):?(\d{2})?\s*-\s*(\d{1,2}):?(\d{2})?(?:\s*([ap]m))?', context)
    if time_range_match:
        try:
            # Extract start and end times
            start_hour = int(time_range_match.group(1))
            start_minute = int(time_range_match.group(2) or 0)
            end_hour = int(time_range_match.group(3))
            end_minute = int(time_range_match.group(4) or 0)
            
            # Handle am/pm
            period = time_range_match.group(5)
            if period and period.lower() == 'pm':
                if start_hour < 12:
                    start_hour += 12
                if end_hour < 12:
                    end_hour += 12
            
            # Calculate duration in minutes
            start_time = start_hour * 60 + start_minute
            end_time = end_hour * 60 + end_minute
            
            # Handle cases where end time is on the next day
            if end_time < start_time:
                end_time += 24 * 60
                
            return end_time - start_time
            
        except (ValueError, TypeError):
            pass
    
    # Look for explicit duration mentions like "2 hours" or "90 minutes"
    duration_match = re.search(r'(\d+)\s*(hour|hr|minute|min)s?', context)
    if duration_match:
        try:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2).lower()
            
            if unit.startswith('hour') or unit.startswith('hr'):
                return amount * 60
            elif unit.startswith('minute') or unit.startswith('min'):
                return amount
                
        except (ValueError, TypeError):
            pass
    
    # Fall back to default duration based on event type
    return default_durations.get(event_data.get('event_type'), 60)