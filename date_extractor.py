"""
date_extractor.py - Module for extracting dates and events from syllabus text
"""
import re
import dateutil.parser
import dateutil.rrule
from datetime import datetime, timedelta
import logging
import spacy
import calendar

logger = logging.getLogger(__name__)

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("SpaCy model not found. Please download it with 'python -m spacy download en_core_web_sm'")
    nlp = None

class DateExtractor:
    """Class to extract dates and categorize events from text."""
    
    EVENT_TYPES = {
        'exam': ['exam', 'midterm', 'final', 'test', 'assessment'],
        'quiz': ['quiz', 'quizzes'],
        'homework': ['homework', 'assignment', 'hw', 'problem set'],
        'project': ['project', 'presentation', 'report'],
        'lab': ['lab', 'laboratory', 'practical']
    }
    
    def __init__(self, year=None, default_event_type="deadline"):
        """
        Initialize the date extractor.
        
        Args:
            year (int, optional): The year to use for dates that don't specify a year
            default_event_type (str): The default event type if none is detected
        """
        self.year = year or datetime.now().year
        self.default_event_type = default_event_type
        
    def extract_dates(self, text):
        """
        Extract all dates and associated events from the text.
        
        Args:
            text (str): The text to extract dates from
            
        Returns:
            list: A list of dictionaries, each containing date and event information
        """
        events = []
        
        # Split text into sections and paragraphs for context
        sections = self._split_into_sections(text)
        
        for section_title, section_text in sections:
            # Determine if this section is about a specific event type
            section_event_type = self._determine_section_event_type(section_title)
            
            # Find dates in this section
            dates = self._find_dates_in_text(section_text)
            
            for date_info in dates:
                # Extract text around the date for context
                context = self._extract_context(section_text, date_info['span'])
                
                # Determine event type based on context and section title
                event_type = self._determine_event_type(context) or section_event_type or self.default_event_type
                
                # Extract event title
                event_title = self._extract_event_title(context, event_type)
                
                events.append({
                    'date': date_info['date'],
                    'original_text': date_info['original'],
                    'event_type': event_type,
                    'title': event_title,
                    'context': context,
                    'section': section_title
                })
        
        return events
    
    def _split_into_sections(self, text):
        """
        Split the text into sections based on headings.
        
        Args:
            text (str): The text to split
            
        Returns:
            list: A list of tuples (section_title, section_content)
        """
        # This is a simplified approach. For real-world use, we'd need more sophisticated section detection
        sections = []
        current_section = ('', '')  # (title, content)
        
        lines = text.split('\n')
        for line in lines:
            # Heuristic: If a line is short, all caps, and followed by a blank line, it might be a heading
            if len(line.strip()) < 50 and line.isupper() and len(line.strip()) > 0:
                # Save the previous section if it has content
                if current_section[1].strip():
                    sections.append(current_section)
                
                # Start a new section
                current_section = (line.strip(), '')
            else:
                # Add to the current section
                current_section = (current_section[0], current_section[1] + line + '\n')
        
        # Add the last section
        if current_section[1].strip():
            sections.append(current_section)
        
        # If no sections were detected, treat the whole text as one section
        if not sections:
            sections = [('', text)]
        
        return sections
    
    def _determine_section_event_type(self, section_title):
        """
        Determine the event type based on the section title.
        
        Args:
            section_title (str): The section title
            
        Returns:
            str or None: The determined event type, or None if not determined
        """
        section_title = section_title.lower()
        
        for event_type, keywords in self.EVENT_TYPES.items():
            if any(keyword in section_title for keyword in keywords):
                return event_type
        
        # Special cases for common syllabus sections
        if 'schedule' in section_title or 'calendar' in section_title or 'tentative' in section_title:
            return 'schedule'
            
        return None
    
    def _find_dates_in_text(self, text):
        """
        Find all dates in the text.
        
        Args:
            text (str): The text to search for dates
            
        Returns:
            list: A list of dictionaries with date information
        """
        dates = []
        
        # Various date formats to look for
        date_patterns = [
            # MM/DD/YYYY or MM-DD-YYYY
            r'\b(0?[1-9]|1[0-2])[/\-](0?[1-9]|[12][0-9]|3[01])[/\-](20\d{2})\b',
            
            # MM/DD or MM-DD (no year)
            r'\b(0?[1-9]|1[0-2])[/\-](0?[1-9]|[12][0-9]|3[01])\b',
            
            # Month DD, YYYY
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?,?\s+(20\d{2})\b',
            
            # Month DD (no year)
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?\b',
            
            # DD Month YYYY
            r'\b(0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)[,]?\s+(20\d{2})\b',
            
            # DD Month (no year)
            r'\b(0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\b',
            
            # Month YYYY (for month-long events)
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b',
            
            # Special format: M/D or M/D/YY
            r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2}))?\b',
            
            # Format like 1/17, with month first
            r'\b(\d{1,2})/(\d{1,2})\b',
            
            # Class Session format (Spring 2023): 2/14 Lec5
            r'\b(\d{1,2})/(\d{1,2})\s+Lec\d+\b'
        ]
        
        for pattern in date_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    date_str = match.group(0)
                    # Try to parse the date
                    parsed_date = self._parse_date(date_str)
                    
                    if parsed_date:
                        dates.append({
                            'date': parsed_date,
                            'original': date_str,
                            'span': match.span()
                        })
                except Exception as e:
                    logger.debug(f"Error parsing date '{match.group(0)}': {str(e)}")
                    continue
        
        return dates
    
    def _parse_date(self, date_str):
        """
        Parse a date string into a datetime object.
        
        Args:
            date_str (str): The date string to parse
            
        Returns:
            datetime or None: The parsed date, or None if parsing failed
        """
        try:
            # Try to parse with dateutil
            parsed_date = dateutil.parser.parse(date_str, fuzzy=True)
            
            # If year is not specified and we have a default year
            if parsed_date.year < 100 and self.year:
                parsed_date = parsed_date.replace(year=self.year)
                
            return parsed_date
            
        except (ValueError, OverflowError):
            # Try to handle special cases
            
            # Format: MM/DD or MM-DD or similar
            match = re.match(r'(\d{1,2})[/\-](\d{1,2})', date_str)
            if match:
                month, day = int(match.group(1)), int(match.group(2))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime(self.year, month, day)
            
            # Format: DD Month
            month_names = list(calendar.month_name)[1:] + list(calendar.month_abbr)[1:]
            for month_name in month_names:
                if month_name.lower() in date_str.lower():
                    for day in range(1, 32):
                        day_patterns = [f" {day} ", f" {day},", f" {day}$", 
                                      f" {day}st ", f" {day}nd ", f" {day}rd ", f" {day}th "]
                        for pattern in day_patterns:
                            if pattern.lower() in date_str.lower():
                                month_idx = (
                                    list(calendar.month_name).index(month_name)
                                    if month_name in calendar.month_name
                                    else list(calendar.month_abbr).index(month_name)
                                )
                                return datetime(self.year, month_idx, day)
            
            logger.debug(f"Could not parse date: {date_str}")
            return None
    
    def _extract_context(self, text, span, context_size=100):
        """
        Extract text around a date mention for context.
        
        Args:
            text (str): The full text
            span (tuple): The (start, end) position of the date in the text
            context_size (int): The number of characters to include before and after
            
        Returns:
            str: The context text
        """
        start, end = span
        context_start = max(0, start - context_size)
        context_end = min(len(text), end + context_size)
        
        # Try to extend to sentence boundaries
        while context_start > 0 and text[context_start] not in '.!?\n':
            context_start -= 1
            
        while context_end < len(text) - 1 and text[context_end] not in '.!?\n':
            context_end += 1
            
        return text[context_start:context_end].strip()
    
    def _determine_event_type(self, context):
        """
        Determine the event type based on the context.
        
        Args:
            context (str): The context text around the date
            
        Returns:
            str or None: The determined event type, or None if not determined
        """
        context_lower = context.lower()
        
        # Check for each event type
        for event_type, keywords in self.EVENT_TYPES.items():
            if any(re.search(rf'\b{re.escape(keyword)}\b', context_lower) for keyword in keywords):
                return event_type
                
        # Check for due dates which could be any type
        if 'due' in context_lower or 'deadline' in context_lower:
            # Look for clues about what type of assignment is due
            for event_type, keywords in self.EVENT_TYPES.items():
                if any(keyword in context_lower for keyword in keywords):
                    return event_type
            return 'deadline'
            
        return None
    
    def _extract_event_title(self, context, event_type):
        """
        Extract a title for the event based on context.
        
        Args:
            context (str): The context text around the date
            event_type (str): The type of event
            
        Returns:
            str: The extracted event title
        """
        # This is a simplified approach. For real-world use, we'd want to use NLP techniques
        # to extract the most relevant noun phrases
        
        # Default title based on event type
        default_title = f"{event_type.title()}"
        
        # Look for numbered instances like "Homework 1" or "Quiz 2"
        match = re.search(rf'\b{re.escape(event_type)}\s+(\d+)', context, re.IGNORECASE)
        if match:
            return f"{event_type.title()} {match.group(1)}"
        
        # Look for titled instances like "Midterm Exam: Data Structures"
        match = re.search(rf'\b{re.escape(event_type)}[:\s]+([^.!?\n]+)', context, re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
        return default_title


class SyllabusEventExtractor:
    """
    Main class for extracting events from a syllabus.
    Combines the PDF extraction and date extraction processes.
    """
    
    def __init__(self, year=None):
        """
        Initialize the syllabus event extractor.
        
        Args:
            year (int, optional): The year to use for dates that don't specify a year
        """
        self.pdf_extractor = None  # Will be initialized when needed
        self.date_extractor = DateExtractor(year=year)
    
    def process_syllabus(self, pdf_file, course_name=None):
        """
        Process a syllabus PDF and extract events.
        
        Args:
            pdf_file: A file-like object containing the PDF
            course_name (str, optional): The name of the course
            
        Returns:
            list: A list of event dictionaries
        """
        # Lazy initialization of PDF extractor
        if self.pdf_extractor is None:
            from pdf_extractor import PDFExtractor
            self.pdf_extractor = PDFExtractor()
        
        # Extract text from PDF
        text = self.pdf_extractor.extract_text(pdf_file)
        
        # Extract dates and events
        events = self.date_extractor.extract_dates(text)
        
        # Add course name to events if provided
        if course_name:
            for event in events:
                event['course'] = course_name
        
        return events

# Testing function
def test_extract_dates(text, year=None):
    """
    Test function to extract dates from text.
    
    Args:
        text (str): The text to extract dates from
        year (int, optional): The year to use for dates that don't specify a year
        
    Returns:
        list: A list of extracted events
    """
    extractor = DateExtractor(year=year)
    return extractor.extract_dates(text)

if __name__ == "__main__":
    # Example usage
    test_text = """
    The midterm exam will be on February 15, 2023. 
    Homework 1 is due on 3/15.
    The final exam is scheduled for May 10th from 7-9pm.
    """
    
    events = test_extract_dates(test_text, year=2023)
    for event in events:
        print(f"Date: {event['date']}")
        print(f"Type: {event['event_type']}")
        print(f"Title: {event['title']}")
        print(f"Original text: {event['original_text']}")
        print("-" * 40)