"""
app.py - Generates token file, run if Google authorization is failing
"""
import os
from calendar_integration import GoogleCalendarIntegration

print("Starting Google Calendar authentication...")

# Remove any existing token file
token_path = 'token.json'
if os.path.exists(token_path):
    print(f"Removing existing token file: {token_path}")
    os.remove(token_path)

# Create calendar integration instance
google_calendar = GoogleCalendarIntegration()

# Try to authenticate
if google_calendar.authenticate():
    print("Authentication successful!")
    # Test listing calendars
    calendars = google_calendar.list_calendars()
    print(f"Found {len(calendars)} calendars")
    for cal in calendars:
        print(f"- {cal.get('summary')} (ID: {cal.get('id')})")
else:
    print("Authentication failed.")