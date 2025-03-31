"""
syllabus_processors.py - Custom processors for specific syllabus formats
"""
import re
import logging
from datetime import datetime, timedelta
import dateutil.parser

logger = logging.getLogger(__name__)

class BaseSyllabusProcessor:
    """Base class for syllabus processors."""
    
    def __init__(self, text, year=None):
        """
        Initialize the processor.
        
        Args:
            text (str): The extracted text from the syllabus
            year (int, optional): The year to use for dates that don't specify a year
        """
        self.text = text
        self.year = year or datetime.now().year
        
    def process(self):
        """
        Process the syllabus to extract events.
        
        Returns:
            list: A list of event dictionaries
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def _extract_course_info(self):
        """
        Extract basic course information.
        
        Returns:
            dict: A dictionary of course information
        """
        # Try to find course code and title
        course_code_match = re.search(r'\b([A-Z]{2,4}[- ]?\d{3}[A-Z]?)\b', self.text)
        course_code = course_code_match.group(1) if course_code_match else None
        
        # Look for common title patterns
        title_patterns = [
            # Format: "COURSE 101: Course Title"
            (re.escape(course_code) + ': (.+?)(?:\n|$)') if course_code else r'[A-Z]{2,4}[- ]?\d{3}[A-Z]?: (.+?)(?:\n|$)',
            
            # Format: "Course Title - COURSE 101"
            r'(.+?) - [A-Z]{2,4}[- ]?\d{3}[A-Z]?',
            
            # Format: "Course Title (COURSE 101)"
            r'(.+?) \([A-Z]{2,4}[- ]?\d{3}[A-Z]?\)'
        ]
        
        course_title = None
        for pattern in title_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                course_title = match.group(1).strip()
                break
        
        # Try to find instructor
        instructor_match = re.search(r'(?:Instructor|Professor|Prof\.):?\s*([^,\n]+)', self.text, re.IGNORECASE)
        instructor = instructor_match.group(1).strip() if instructor_match else None
        
        # Try to find term/semester
        term_match = re.search(r'(?:Term|Semester|Quarter):?\s*([^,\n]+)', self.text, re.IGNORECASE)
        term = term_match.group(1).strip() if term_match else None
        
        # If term not found, look for patterns like "Spring 2023"
        if not term:
            seasons = ['Spring', 'Summer', 'Fall', 'Winter']
            for season in seasons:
                match = re.search(rf'{season}\s+(\d{{4}})', self.text, re.IGNORECASE)
                if match:
                    term = f"{season} {match.group(1)}"
                    break
        
        return {
            'course_code': course_code,
            'course_title': course_title,
            'instructor': instructor,
            'term': term
        }


class ScheduleTableProcessor(BaseSyllabusProcessor):
    """
    Processor for syllabi that contain schedule tables.
    Especially useful for CS course syllabi with well-defined weekly schedules.
    """
    
    def process(self):
        """
        Process the syllabus to extract events from schedule tables.
        
        Returns:
            list: A list of event dictionaries
        """
        events = []
        
        # First, extract basic course info
        course_info = self._extract_course_info()
        
        # Try to find a schedule table
        # Look for sections that might contain schedules
        schedule_sections = self._extract_schedule_sections()
        
        for section_title, section_text in schedule_sections:
            section_events = self._process_schedule_section(section_title, section_text)
            
            # Add course info to each event
            for event in section_events:
                event.update({
                    'course_code': course_info.get('course_code'),
                    'course': course_info.get('course_title') or course_info.get('course_code', 'Unknown Course')
                })
                
            events.extend(section_events)
        
        return events
    
    def _extract_schedule_sections(self):
        """
        Extract sections that might contain schedule information.
        
        Returns:
            list: A list of tuples (section_title, section_text)
        """
        sections = []
        
        # Common section titles that might contain schedules
        schedule_keywords = [
            'schedule', 'calendar', 'outline', 'tentative', 'weekly', 
            'topics', 'lectures', 'course plan', 'syllabus'
        ]
        
        # Split text into sections
        current_section = ('', '')
        lines = self.text.split('\n')
        
        for i, line in enumerate(lines):
            # Check if this line might be a section title
            line_lower = line.strip().lower()
            
            # If line is short, potentially a heading, and contains schedule keywords
            if len(line.strip()) < 50 and len(line.strip()) > 3 and any(keyword in line_lower for keyword in schedule_keywords):
                # Save previous section if it exists
                if current_section[1].strip():
                    sections.append(current_section)
                
                # Start new section
                current_section = (line.strip(), '')
                
            elif current_section[0]:  # If we're in a section
                current_section = (current_section[0], current_section[1] + line + '\n')
        
        # Add the last section
        if current_section[1].strip():
            sections.append(current_section)
        
        return sections
    
    def _process_schedule_section(self, section_title, section_text):
        """
        Process a section that might contain schedule information.
        
        Args:
            section_title (str): The title of the section
            section_text (str): The text of the section
            
        Returns:
            list: A list of event dictionaries extracted from the section
        """
        events = []
        
        # Try to identify if this is a weekly schedule or a list of key dates
        is_weekly_schedule = False
        week_keywords = ['week', 'session', 'class', 'day', 'date', 'topic']
        
        if any(keyword in section_title.lower() for keyword in week_keywords):
            is_weekly_schedule = True
        
        # Check for table-like structures (rows with consistent patterns)
        lines = section_text.split('\n')
        structured_rows = []
        
        # Look for patterns like "Week X: Topic" or "MM/DD: Topic"
        for line in lines:
            # Date pattern: MM/DD
            date_match = re.search(r'(\d{1,2}/\d{1,2})', line)
            
            # Week pattern: Week X or Session X
            week_match = re.search(r'(Week|Session)\s+(\d+)', line, re.IGNORECASE)
            
            # Extract topic after date or week
            if date_match or week_match:
                marker = date_match.group(1) if date_match else f"{week_match.group(1)} {week_match.group(2)}"
                # Get the part after the marker, which is likely the topic
                parts = line.split(marker, 1)
                if len(parts) > 1:
                    topic = parts[1].strip(':- \t')
                    structured_rows.append((marker, topic))
        
        # Process structured rows if found
        if structured_rows:
            for marker, topic in structured_rows:
                # For date markers, create specific events
                if re.match(r'\d{1,2}/\d{1,2}', marker):
                    try:
                        # Parse the date
                        month, day = map(int, marker.split('/'))
                        
                        # Create the date object
                        event_date = datetime(self.year, month, day)
                        
                        # Determine event type based on topic
                        event_type = self._determine_event_type(topic)
                        
                        events.append({
                            'date': event_date,
                            'title': topic,
                            'event_type': event_type,
                            'original_text': f"{marker}: {topic}",
                            'context': section_title,
                            'section': section_title
                        })
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Error parsing date from marker '{marker}': {str(e)}")
                
                # For week markers, less specific but still useful
                elif re.match(r'(Week|Session)\s+\d+', marker, re.IGNORECASE):
                    # Cannot determine exact date, but still track topic for reference
                    # Could potentially calculate dates if first day of class is known
                    pass
        
        # Look for event mentions within the text
        events.extend(self._extract_events_from_text(section_text, section_title))
        
        return events
    
    def _determine_event_type(self, topic):
        """
        Determine the event type based on the topic description.
        
        Args:
            topic (str): The topic description
            
        Returns:
            str: The determined event type
        """
        topic_lower = topic.lower()
        
        # Check for specific event types
        if any(keyword in topic_lower for keyword in ['exam', 'midterm', 'final', 'test']):
            return 'exam'
        elif any(keyword in topic_lower for keyword in ['quiz']):
            return 'quiz'
        elif any(keyword in topic_lower for keyword in ['homework', 'assignment', 'hw', 'problem set']):
            return 'homework'
        elif any(keyword in topic_lower for keyword in ['project', 'presentation']):
            return 'project'
        elif any(keyword in topic_lower for keyword in ['lab', 'practical']):
            return 'lab'
        elif any(keyword in topic_lower for keyword in ['due', 'deadline']):
            # Try to determine what type of thing is due
            if 'homework' in topic_lower or 'hw' in topic_lower:
                return 'homework'
            elif 'project' in topic_lower:
                return 'project'
            elif 'lab' in topic_lower:
                return 'lab'
            else:
                return 'deadline'
        
        # Default to class session
        return 'schedule'
    
    def _extract_events_from_text(self, text, section_title):
        """
        Extract events mentioned directly in the text.
        
        Args:
            text (str): The text to extract events from
            section_title (str): The title of the section
            
        Returns:
            list: A list of event dictionaries
        """
        events = []
        
        # Common event keywords
        event_keywords = {
            'exam': ['exam', 'midterm', 'final', 'test'],
            'quiz': ['quiz'],
            'homework': ['homework', 'assignment', 'hw', 'problem set'],
            'project': ['project', 'presentation', 'report'],
            'lab': ['lab', 'laboratory', 'practical']
        }
        
        # Scan for event mentions near dates
        for event_type, keywords in event_keywords.items():
            for keyword in keywords:
                # Look for patterns like "Homework 1 due on 3/15"
                pattern = rf'({keyword}\s+\d+).*?(\d{{1,2}}/\d{{1,2}})'
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    event_title = match.group(1).strip()
                    date_str = match.group(2).strip()
                    
                    try:
                        month, day = map(int, date_str.split('/'))
                        event_date = datetime(self.year, month, day)
                        
                        events.append({
                            'date': event_date,
                            'title': event_title,
                            'event_type': event_type,
                            'original_text': match.group(0),
                            'context': text[max(0, match.start() - 50):min(len(text), match.end() + 50)],
                            'section': section_title
                        })
                    except (ValueError, TypeError):
                        continue
                
                # Look for patterns like "3/15: Homework 1 due"
                pattern = rf'(\d{{1,2}}/\d{{1,2}}).*?({keyword}\s+\d+)'
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    date_str = match.group(1).strip()
                    event_title = match.group(2).strip()
                    
                    try:
                        month, day = map(int, date_str.split('/'))
                        event_date = datetime(self.year, month, day)
                        
                        events.append({
                            'date': event_date,
                            'title': event_title,
                            'event_type': event_type,
                            'original_text': match.group(0),
                            'context': text[max(0, match.start() - 50):min(len(text), match.end() + 50)],
                            'section': section_title
                        })
                    except (ValueError, TypeError):
                        continue
        
        return events


class CSCISyllabusProcessor(BaseSyllabusProcessor):
    """
    Processor specifically designed for the USC CSCI course syllabi format.
    Based on the examples provided in the original request.
    """
    
    def process(self):
        """
        Process the USC CSCI course syllabus to extract events.
        
        Returns:
            list: A list of event dictionaries
        """
        events = []
        
        # Extract course info
        course_info = self._extract_course_info()
        course_name = course_info.get('course_code', '')
        
        # Process each specific section
        events.extend(self._extract_assignments_from_grading_section())
        events.extend(self._extract_events_from_schedule_section())
        
        # Add course info to all events
        for event in events:
            if 'course' not in event:
                event['course'] = course_name
        
        return events
    
    def _extract_assignments_from_grading_section(self):
        """
        Extract assignment information from the grading section.
        
        Returns:
            list: A list of event dictionaries for assignments
        """
        events = []
        
        # Look for the grading section
        grading_section_match = re.search(r'(?:Grading|Assessment|Evaluation).*?(?=\n\n|\Z)', self.text, re.DOTALL | re.IGNORECASE)
        if not grading_section_match:
            return events
            
        grading_section = grading_section_match.group(0)
        
        # Look for assignment categories and deadlines
        assignment_patterns = [
            # Pattern for "Homework (10): 20%"
            r'(Homework|Projects?|Quizzes|Labs?|Exams?|Midterms?|Finals?|Assignments?)(?:\s+\(?(\d+)\)?)?\s*:?\s*(\d+)%',
            
            # Pattern for "Homework: 20% - Due Mondays 11:59pm"
            r'(Homework|Projects?|Quizzes|Labs?|Exams?|Midterms?|Finals?|Assignments?)[^\n]*Due\s+([^\n]+)',
            
            # Pattern for specific assignment mentions
            r'(Homework|Project|Quiz|Lab|Exam|Midterm|Final|Assignment)\s+(\d+)[^\n]*Due\s+([^\n]+)'
        ]
        
        for pattern in assignment_patterns:
            for match in re.finditer(pattern, grading_section, re.IGNORECASE):
                assignment_type = match.group(1)
                
                # Determine event type
                event_type = self._map_assignment_to_event_type(assignment_type)
                
                if pattern.endswith('(\d+)%'):
                    # This pattern gives us the quantity but not specific dates
                    try:
                        quantity = int(match.group(2)) if match.group(2) else 1
                        # If we have multiple of this type, we'll need to extrapolate
                        # This is tentative and will be improved with the schedule section
                        
                        # Don't create events here, just note the existence and count
                        # for potential schedule matching later
                        pass
                    except (ValueError, TypeError):
                        pass
                else:
                    # This pattern gives us due date information
                    due_info = match.group(2) if pattern.endswith('([^\n]+)') else match.group(3)
                    
                    # Try to extract date information
                    dates = self._extract_dates_from_text(due_info)
                    
                    # If we have a specific assignment number, include it
                    assignment_num = match.group(2) if 'Homework\\s+(\\d+)' in pattern else None
                    
                    for date in dates:
                        title = f"{assignment_type}"
                        if assignment_num:
                            title += f" {assignment_num}"
                            
                        events.append({
                            'date': date,
                            'title': title,
                            'event_type': event_type,
                            'original_text': match.group(0),
                            'context': grading_section,
                            'section': 'Grading'
                        })
        
        return events
    
    def _extract_events_from_schedule_section(self):
        """
        Extract events from the course schedule section.
        
        Returns:
            list: A list of event dictionaries
        """
        events = []
        
        # Look for schedule section
        schedule_patterns = [
            r'(?:Course\s+Schedule|Tentative\s+Schedule|Schedule|Weekly\s+Breakdown).*?(?=\n\n\w|\Z)',
            r'(?:Week|Day|Date|Topic).*?(?=\n\n\w|\Z)'
        ]
        
        schedule_section = None
        for pattern in schedule_patterns:
            match = re.search(pattern, self.text, re.DOTALL | re.IGNORECASE)
            if match:
                schedule_section = match.group(0)
                break
        
        if not schedule_section:
            return events
        
        # Look for table-like structures
        lines = schedule_section.split('\n')
        
        # USC CSCI syllabus often uses a format like:
        # 1/10 Introduction Ch. 1 HW 0 Out
        # 1/12 Pigeon-Hole Principle
        
        # Pattern to match date at beginning of line
        date_pattern = r'^(?:\s*)(\d{1,2}/\d{1,2})\s+(.+)'
        
        for line in lines:
            match = re.match(date_pattern, line)
            if match:
                date_str = match.group(1)
                content = match.group(2)
                
                try:
                    month, day = map(int, date_str.split('/'))
                    event_date = datetime(self.year, month, day)
                    
                    # Process the content to determine event type and title
                    # First, check for specific event keywords
                    event_info = self._extract_event_info_from_line(content)
                    
                    if event_info:
                        events.append({
                            'date': event_date,
                            'title': event_info['title'],
                            'event_type': event_info['type'],
                            'original_text': line,
                            'context': schedule_section,
                            'section': 'Schedule'
                        })
                    else:
                        # If no specific event, it's likely a lecture topic
                        events.append({
                            'date': event_date,
                            'title': f"Lecture: {content}",
                            'event_type': 'schedule',
                            'original_text': line,
                            'context': schedule_section,
                            'section': 'Schedule'
                        })
                        
                except (ValueError, TypeError):
                    continue
        
        return events
    
    def _extract_event_info_from_line(self, content):
        """
        Extract event information from a schedule line content.
        
        Args:
            content (str): The content text
            
        Returns:
            dict or None: Event information dict or None if no event found
        """
        content_lower = content.lower()
        
        # Check for homework/assignment release or due dates
        hw_out_match = re.search(r'(HW|Homework|Assignment)\s+(\d+)\s+(?:Out|Released|Assigned)', content, re.IGNORECASE)
        if hw_out_match:
            return {
                'title': f"{hw_out_match.group(1)} {hw_out_match.group(2)} Released",
                'type': 'homework'
            }
            
        hw_due_match = re.search(r'(HW|Homework|Assignment)\s+(\d+)\s+(?:Due|Deadline)', content, re.IGNORECASE)
        if hw_due_match:
            return {
                'title': f"{hw_due_match.group(1)} {hw_due_match.group(2)} Due",
                'type': 'homework'
            }
            
        # Check for quiz dates
        quiz_match = re.search(r'(Quiz)\s+(\d+)', content, re.IGNORECASE)
        if quiz_match:
            return {
                'title': f"{quiz_match.group(1)} {quiz_match.group(2)}",
                'type': 'quiz'
            }
            
        # Check for exam dates
        exam_match = re.search(r'(Midterm|Final|Exam)\s+(\d*)', content, re.IGNORECASE)
        if exam_match:
            num = exam_match.group(2) if exam_match.group(2) else ""
            return {
                'title': f"{exam_match.group(1)} {num}".strip(),
                'type': 'exam'
            }
            
        # Check for project dates
        project_match = re.search(r'(Project)\s+(\d+)\s+(?:Out|Released|Assigned|Due|Deadline)', content, re.IGNORECASE)
        if project_match:
            action = "Due" if "due" in content_lower or "deadline" in content_lower else "Released"
            return {
                'title': f"{project_match.group(1)} {project_match.group(2)} {action}",
                'type': 'project'
            }
        
        # No specific event found
        return None
    
    def _extract_dates_from_text(self, text):
        """
        Extract dates from text descriptions like "Mondays 11:59pm".
        
        Args:
            text (str): The text to extract dates from
            
        Returns:
            list: A list of datetime objects for the dates
        """
        dates = []
        text_lower = text.lower()
        
        # Check for specific date mentions
        date_match = re.search(r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)', text)
        if date_match:
            try:
                date_parts = date_match.group(1).split('/')
                if len(date_parts) == 2:
                    month, day = map(int, date_parts)
                    dates.append(datetime(self.year, month, day))
                elif len(date_parts) == 3:
                    month, day, year = map(int, date_parts)
                    if year < 100:
                        year += 2000
                    dates.append(datetime(year, month, day))
            except (ValueError, TypeError):
                pass
        
        # Check for day of week mentions like "Mondays"
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day_name in enumerate(day_names):
            if day_name in text_lower or day_name[:-1] in text_lower:  # Check both "monday" and "mondays"
                # Without specific dates, we'd need to calculate based on term start
                # For now, we'll skip this as we need more context
                pass
        
        # Check for specific dates like "Wednesday, May 10th"
        date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?', text, re.IGNORECASE)
        if date_match:
            try:
                month_name = date_match.group(1)
                day = int(date_match.group(2))
                
                month_names = ['january', 'february', 'march', 'april', 'may', 'june', 
                              'july', 'august', 'september', 'october', 'november', 'december']
                month = month_names.index(month_name.lower()) + 1
                
                dates.append(datetime(self.year, month, day))
            except (ValueError, TypeError):
                pass
        
        return dates
    
    def _map_assignment_to_event_type(self, assignment_type):
        """
        Map assignment type string to standardized event type.
        
        Args:
            assignment_type (str): The assignment type string
            
        Returns:
            str: The standardized event type
        """
        assignment_type_lower = assignment_type.lower()
        
        if 'homework' in assignment_type_lower or 'assignment' in assignment_type_lower:
            return 'homework'
        elif 'project' in assignment_type_lower:
            return 'project'
        elif 'quiz' in assignment_type_lower:
            return 'quiz'
        elif 'exam' in assignment_type_lower or 'midterm' in assignment_type_lower or 'final' in assignment_type_lower:
            return 'exam'
        elif 'lab' in assignment_type_lower:
            return 'lab'
        else:
            return 'deadline'


# Factory function to select the appropriate processor
def get_syllabus_processor(text, year=None):
    """
    Factory function to select the appropriate syllabus processor.
    
    Args:
        text (str): The extracted text from the syllabus
        year (int, optional): The year to use for dates that don't specify a year
        
    Returns:
        BaseSyllabusProcessor: The appropriate processor for the syllabus
    """
    # Check for USC CSCI course indicators
    if re.search(r'CSCI[- ]?\d{3}', text) and 'USC' in text:
        return CSCISyllabusProcessor(text, year)
    
    # Default to schedule table processor for most syllabi
    return ScheduleTableProcessor(text, year)