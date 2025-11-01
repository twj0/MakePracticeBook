"""
File Converter Module - Convert docx/doc/pdf files to Markdown format
"""

import re
from typing import Optional
from pathlib import Path
import io


class FileConverter:
    """File converter class supporting docx/doc/pdf to Markdown conversion"""
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize file converter
        
        Args:
            tesseract_cmd: Path to tesseract executable (optional)
        """
        if tesseract_cmd:
            # Lazy import only when explicitly provided to avoid import cost on cold start
            import pytesseract  # type: ignore
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    def convert_to_markdown(self, file_path: str) -> str:
        """
        Convert file to Markdown format
        
        Args:
            file_path: Path to input file
            
        Returns:
            str: Markdown formatted content
            
        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = file_path.suffix.lower()
        
        if suffix == '.pdf':
            return self._convert_pdf_to_markdown(str(file_path))
        elif suffix == '.docx':
            return self._convert_docx_to_markdown(str(file_path))
        elif suffix == '.doc':
            raise ValueError(".doc (legacy) is not supported. Please convert to .docx first.")
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Supported: .docx, .pdf")
    
    def _convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """
        Convert PDF to Markdown, using OCR for scanned PDFs
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            str: Markdown formatted content
        """
        try:
            # Lazy import PyMuPDF
            import fitz  # type: ignore
            doc = fitz.open(pdf_path)
            markdown_content = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Try to extract text directly
                text = page.get_text()
                
                # If no text found or very little text, use OCR
                if not text.strip() or len(text.strip()) < 50:
                    text = self._ocr_page(page)
                
                if text.strip():
                    markdown_content.append(f"## Page {page_num + 1}\n\n{text}\n")
            
            doc.close()
            return "\n".join(markdown_content)
            
        except Exception as e:
            raise Exception(f"Failed to convert PDF: {str(e)}")
    
    def _ocr_page(self, page) -> str:
        """
        Perform OCR on a PDF page
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            str: Extracted text
        """
        try:
            # Lazy imports for OCR pipeline
            import fitz  # type: ignore
            from PIL import Image  # type: ignore
            import numpy as np  # type: ignore
            import cv2  # type: ignore
            import pytesseract  # type: ignore

            # Convert page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
            img_data = pix.tobytes("png")
            
            # Convert to PIL Image
            image = Image.open(io.BytesIO(img_data))
            
            # Convert to numpy array for OpenCV processing
            img_array = np.array(image)
            
            # Preprocess image for better OCR results
            # Convert to grayscale
            if len(img_array.shape) == 3:
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_array
            
            # Apply thresholding to get better contrast
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(binary)
            
            # Convert back to PIL Image for pytesseract
            processed_image = Image.fromarray(denoised)
            
            # Perform OCR with Chinese and English support
            text = pytesseract.image_to_string(
                processed_image,
                lang='chi_sim+eng',  # Chinese Simplified + English
                config='--psm 6'  # Assume a single uniform block of text
            )
            
            return text
            
        except Exception as e:
            # If OCR fails, return empty string
            print(f"Warning: OCR failed for page: {str(e)}")
            return ""
    
    def _convert_docx_to_markdown(self, docx_path: str) -> str:
        """
        Convert DOCX to Markdown
        
        Args:
            docx_path: Path to DOCX file
            
        Returns:
            str: Markdown formatted content
        """
        try:
            # Import python-docx (not in pyproject.toml yet)
            try:
                from docx import Document
            except ImportError:
                raise ImportError(
                    "python-docx is required for DOCX conversion. "
                    "Please install it: pip install python-docx"
                )
            
            doc = Document(docx_path)
            markdown_content = []
            
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue
                
                # Check paragraph style and convert to markdown
                style = paragraph.style.name.lower()
                
                if 'heading 1' in style or 'title' in style:
                    markdown_content.append(f"# {text}\n")
                elif 'heading 2' in style:
                    markdown_content.append(f"## {text}\n")
                elif 'heading 3' in style:
                    markdown_content.append(f"### {text}\n")
                elif 'heading 4' in style:
                    markdown_content.append(f"#### {text}\n")
                else:
                    markdown_content.append(f"{text}\n")
            
            # Process tables
            for table in doc.tables:
                markdown_content.append(self._convert_table_to_markdown(table))
            
            return "\n".join(markdown_content)
            
        except Exception as e:
            raise Exception(f"Failed to convert DOCX: {str(e)}")
    
    def _convert_table_to_markdown(self, table) -> str:
        """
        Convert a DOCX table to Markdown format
        
        Args:
            table: python-docx table object
            
        Returns:
            str: Markdown formatted table
        """
        markdown_table = ["\n"]
        
        for i, row in enumerate(table.rows):
            cells = [cell.text.strip() for cell in row.cells]
            markdown_table.append("| " + " | ".join(cells) + " |")
            
            # Add separator after header row
            if i == 0:
                markdown_table.append("| " + " | ".join(["---"] * len(cells)) + " |")
        
        markdown_table.append("\n")
        return "\n".join(markdown_table)
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean and normalize text
        
        Args:
            text: Input text
            
        Returns:
            str: Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        # Remove BOM and other special characters
        text = text.replace('\ufeff', '')
        
        return text.strip()


# Utility function for quick conversion
def convert_file(input_path: str, output_path: Optional[str] = None) -> str:
    """
    Quick conversion utility function
    
    Args:
        input_path: Path to input file
        output_path: Path to output file (optional)
        
    Returns:
        str: Markdown content
    """
    converter = FileConverter()
    markdown_content = converter.convert_to_markdown(input_path)
    markdown_content = FileConverter.clean_text(markdown_content)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
    
    return markdown_content


def convert_file_to_markdown(input_path: str, tesseract_cmd: Optional[str] = None) -> str:
    """
    Convert a file (docx/doc/pdf) to Markdown text only (no file writing).
    Intended for GUI usage.
    
    Args:
        input_path: Path to the input file
        tesseract_cmd: Path to the Tesseract executable (optional)
    
    Returns:
        str: Markdown content
    """
    converter = FileConverter(tesseract_cmd=tesseract_cmd)
    markdown_content = converter.convert_to_markdown(input_path)
    return FileConverter.clean_text(markdown_content)
