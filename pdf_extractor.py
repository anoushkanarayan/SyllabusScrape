"""
pdf_extractor.py - Module for extracting text from PDF syllabi
"""
import io
from pdfminer.converter import TextConverter
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.layout import LAParams
import logging
import re

logger = logging.getLogger(__name__)

class PDFExtractor:
    """Class to handle the extraction of text from PDF files."""
    
    def __init__(self, detect_tables=True):
        """
        Initialize the PDF extractor.
        
        Args:
            detect_tables (bool): Whether to attempt to detect and preserve table structures
        """
        self.detect_tables = detect_tables
        
    def extract_text(self, pdf_file):
        """
        Extract text from a PDF file.
        
        Args:
            pdf_file: A file-like object containing the PDF
            
        Returns:
            str: The extracted text
        """
        try:
            resource_manager = PDFResourceManager()
            fake_file_handle = io.StringIO()
            
            # Set parameters for text extraction
            laparams = LAParams(
                line_margin=0.5,
                word_margin=0.1,
                char_margin=2.0,
                all_texts=True
            )
            
            converter = TextConverter(
                resource_manager, 
                fake_file_handle, 
                laparams=laparams
            )
            
            page_interpreter = PDFPageInterpreter(resource_manager, converter)
            
            # Extract text from each page
            for page in PDFPage.get_pages(pdf_file, check_extractable=True):
                page_interpreter.process_page(page)
                
            text = fake_file_handle.getvalue()
            
            # Clean up
            converter.close()
            fake_file_handle.close()
            
            # Post-process the text
            return self._post_process_text(text)
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
    
    def _post_process_text(self, text):
        """
        Clean and normalize the extracted text.
        
        Args:
            text (str): The raw extracted text
            
        Returns:
            str: The processed text
        """
        # Replace multiple newlines with a single one
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Try to identify and preserve table structures if requested
        if self.detect_tables:
            # This is a simplified approach - real table detection would be more complex
            # Look for lines with patterns that suggest a table row (multiple spaces between words)
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if re.search(r'\S+\s{2,}\S+', line):
                    # This could be a table row, preserve its formatting
                    lines[i] = "TABLE_ROW: " + line
            
            text = '\n'.join(lines)
        
        return text
    
    def extract_text_by_pages(self, pdf_file):
        """
        Extract text from a PDF file, returning a list of strings, one for each page.
        
        Args:
            pdf_file: A file-like object containing the PDF
            
        Returns:
            list: A list of strings, one per page
        """
        pages_text = []
        
        try:
            for page_num, page in enumerate(PDFPage.get_pages(pdf_file, check_extractable=True)):
                resource_manager = PDFResourceManager()
                fake_file_handle = io.StringIO()
                converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
                page_interpreter = PDFPageInterpreter(resource_manager, converter)
                page_interpreter.process_page(page)
                
                text = fake_file_handle.getvalue()
                pages_text.append(text)
                
                # Clean up
                converter.close()
                fake_file_handle.close()
                
            return pages_text
        
        except Exception as e:
            logger.error(f"Error extracting text from PDF by pages: {str(e)}")
            raise

# Testing function
def test_extract_pdf(pdf_path):
    """
    Test function to extract text from a PDF file at the given path.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        str: The extracted text
    """
    with open(pdf_path, 'rb') as file:
        extractor = PDFExtractor()
        return extractor.extract_text(file)

if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        extracted_text = test_extract_pdf(pdf_path)
        print(extracted_text)
    else:
        print("Please provide a PDF file path")