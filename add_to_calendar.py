"""
add_to_calendar.py - Test file + Google API interaction
"""

import requests
import json
import time

# 1. Upload syllabus and extract events
syllabus_path = "syllabus170.pdf"  # Replace with your syllabus path

with open(syllabus_path, 'rb') as f:
    files = {'file': f}
    data = {'course_name': 'CSCI 170', 'year': '2023'}
    response = requests.post('http://localhost:5000/api/upload', files=files, data=data)

extracted_data = response.json()
print(f"Extracted {len(extracted_data['events'])} events from syllabus")

# 2. Get Google Calendar authorization (this will open a browser for auth)
auth_response = requests.get('http://localhost:5000/api/calendars/google')
calendars = auth_response.json().get('calendars', [])

print("\nAvailable calendars:")
for cal in calendars:
    print(f"- {cal['summary']} (ID: {cal['id']})")

# 3. Add events to Google Calendar
events_array = extracted_data['events']

# Add default titles for events with empty titles
for event in events_array:
    if not event.get('title'):
        event['title'] = f"CSCI 170 Class Session"

# Create the request data
calendar_data = {
    "calendar_id": "primary",  # You can change this to a specific calendar ID
    "events": events_array
}

# Send request to create events
create_response = requests.post(
    'http://localhost:5000/api/events/google',
    json=calendar_data
)

print(f"\nCalendar creation response: {create_response.status_code}")
print(f"Response text: {create_response.text}")

if create_response.status_code == 200:
    print("\nEvents successfully added to your Google Calendar!")
    print("Check https://calendar.google.com/ to view them.")
else:
    print("\nError adding events to calendar. See response above for details.")