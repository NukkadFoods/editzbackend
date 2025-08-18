import fitz  # PyMuPDF
import re
from typing import Dict, List, Tuple

class TextShiftingAnalyzer:
    def __init__(self, pdf_content: bytes, page_num: int = 0):
        self.doc = fitz.open(stream=pdf_content, filetype="pdf")
        self.page_num = page_num
        self.page = self.doc.load_page(page_num)
        self.blocks = self.page.get_text("dict")["blocks"]
        
    def analyze_text_context(self, target_text: str, target_bbox: List[float] = None) -> Dict:
        """
        Analyze the context of target text to determine shifting strategy
        """
        # If bbox is provided, use it for more precise matching
        if target_bbox:
            span_data = self._find_span_by_bbox(target_bbox)
            if span_data:
                return self._analyze_span_context(span_data['span'], span_data['line'], span_data['block'])
        
        # Fallback to text search
        for block in self.blocks:
            if "lines" not in block:
                continue
                
            for line in block["lines"]:
                for span in line["spans"]:
                    if target_text.strip() in span["text"].strip():
                        return self._analyze_span_context(span, line, block)
        
        return self._default_context()
    
    def _find_span_by_bbox(self, target_bbox: List[float]) -> Dict:
        """
        Find span by matching bounding box coordinates
        """
        tolerance = 5.0  # Points tolerance for bbox matching
        
        for block in self.blocks:
            if "lines" not in block:
                continue
                
            for line in block["lines"]:
                for span in line["spans"]:
                    span_bbox = span["bbox"]
                    # Check if bboxes match within tolerance
                    if (abs(span_bbox[0] - target_bbox[0]) < tolerance and
                        abs(span_bbox[1] - target_bbox[1]) < tolerance and
                        abs(span_bbox[2] - target_bbox[2]) < tolerance and
                        abs(span_bbox[3] - target_bbox[3]) < tolerance):
                        return {'span': span, 'line': line, 'block': block}
        
        return None
    
    def _analyze_span_context(self, span: Dict, line: Dict, block: Dict) -> Dict:
        """
        Analyze individual span context
        """
        bbox = span["bbox"]
        text = span["text"].strip()
        
        # Get page dimensions
        page_rect = self.page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        # Calculate positioning ratios
        left_ratio = bbox[0] / page_width
        right_ratio = (page_width - bbox[2]) / page_width
        center_ratio = abs((bbox[0] + bbox[2]) / 2 - page_width / 2) / page_width
        
        # Determine alignment
        alignment = self._determine_alignment(left_ratio, right_ratio, center_ratio)
        
        # Check for bullet/list context
        is_list_item = self._is_list_item(text, line)
        
        # Check for header/title context
        is_header = self._is_header(span, block)
        
        # Check for justified text
        is_justified = self._is_justified(line, page_width)
        
        # Calculate available space
        available_space = {
            'left': bbox[0],
            'right': page_width - bbox[2],
            'above': bbox[1],
            'below': page_height - bbox[3]
        }
        
        return {
            'text': text,
            'original_bbox': bbox,
            'alignment': alignment,
            'is_list_item': is_list_item,
            'is_header': is_header,
            'is_justified': is_justified,
            'left_ratio': round(left_ratio, 3),
            'right_ratio': round(right_ratio, 3),
            'center_ratio': round(center_ratio, 3),
            'available_space': available_space,
            'font_size': span.get("size", 12),
            'line_height': line.get("bbox", [0,0,0,12])[3] - line.get("bbox", [0,0,0,0])[1],
            'page_width': page_width,
            'page_height': page_height
        }
    
    def _determine_alignment(self, left_ratio: float, right_ratio: float, center_ratio: float) -> str:
        """
        Determine text alignment based on positioning ratios with improved logic
        """
        # More strict thresholds for alignment detection
        left_margin_threshold = 0.05   # Very close to left edge = left aligned
        right_margin_threshold = 0.05  # Very close to right edge = right aligned
        center_threshold = 0.02        # Very close to center = center aligned
        
        # Check for left alignment first (most common in documents)
        if left_ratio <= left_margin_threshold:
            return "left"
        
        # Check for right alignment
        elif right_ratio <= right_margin_threshold:
            return "right"
        
        # Check for center alignment (both margins roughly equal AND close to center)
        elif center_ratio <= center_threshold and abs(left_ratio - right_ratio) <= 0.1:
            return "center"
        
        # For everything else, default to left alignment to prevent unwanted shifting
        # This is safer for most document text
        else:
            return "left"
    
    def _is_list_item(self, text: str, line: Dict) -> bool:
        """
        Check if text is part of a list item
        """
        bullet_patterns = [
            r'^[\*\-\•\◦\▪]\s',           # Common bullets
            r'^\d+[\.\)]\s',              # Numbered lists
            r'^[A-Za-z][\.\)]\s',         # Lettered lists
            r'^\([A-Za-z\d]\)\s',         # Parenthesized items
        ]
        
        for pattern in bullet_patterns:
            if re.match(pattern, text.strip()):
                return True
        
        # Check if previous spans contain bullets
        if "spans" in line:
            for prev_span in line["spans"]:
                prev_text = prev_span["text"].strip()
                if prev_text in ['*', '-', '•', '◦', '▪'] or re.match(r'^\d+[\.\)]$', prev_text):
                    return True
        
        return False
    
    def _is_header(self, span: Dict, block: Dict) -> bool:
        """
        Check if text is a header/title
        """
        font_size = span.get("size", 12)
        
        # Check if font size is significantly larger than average
        avg_size = self._calculate_average_font_size()
        is_large = font_size > (avg_size * 1.3)
        
        # Check for header-like text patterns
        text = span["text"].strip()
        is_header_text = bool(re.match(r'^[A-Z][A-Za-z\s]{2,}$', text)) and \
                        len(text.split()) <= 8  # Short phrases
        
        # Check for bold text (likely headers)
        font_flags = span.get("flags", 0)
        is_bold = bool(font_flags & 16)
        
        return is_large or (is_header_text and is_bold)
    
    def _is_justified(self, line: Dict, page_width: float) -> bool:
        """
        Check if line appears to be justified
        """
        line_bbox = line.get("bbox", [0, 0, 0, 0])
        line_width = line_bbox[2] - line_bbox[0]
        
        # If line spans most of page width, likely justified
        return line_width > (page_width * 0.75)
    
    def _calculate_average_font_size(self) -> float:
        """
        Calculate average font size on page
        """
        total_size = 0
        count = 0
        
        for block in self.blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        total_size += span.get("size", 12)
                        count += 1
        
        return total_size / count if count > 0 else 12
    
    def _default_context(self) -> Dict:
        """
        Default context when text not found
        """
        return {
            'text': '',
            'original_bbox': [0, 0, 0, 0],
            'alignment': 'left',
            'is_list_item': False,
            'is_header': False,
            'is_justified': False,
            'left_ratio': 0,
            'right_ratio': 0,
            'center_ratio': 0,
            'available_space': {'left': 0, 'right': 0, 'above': 0, 'below': 0},
            'font_size': 12,
            'line_height': 14,
            'page_width': 595,  # Standard A4 width
            'page_height': 842  # Standard A4 height
        }
    
    def close(self):
        """Close document"""
        self.doc.close()
