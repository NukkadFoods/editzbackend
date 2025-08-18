import re
from typing import List, Dict, Tuple

def detect_text_context(text: str, line_text: str, bbox: tuple, page_width: float, 
                       all_text_items: List[Dict]) -> str:
    """
    Detect if text is isolated (header/title) or part of tabular/continuation content.
    
    Args:
        text: The specific text being edited
        line_text: Full text of the line containing this text
        bbox: (x0, y0, x1, y1) of the text
        page_width: Total width of the page
        all_text_items: All text items on the page for context analysis
    
    Returns:
        'isolated_center' - Isolated text that should be centered
        'table_left' - Table/list content that should shift right
        'table_right' - Table content that should shift left 
        'continuation' - Continuation text that maintains flow
    """
    
    # Get position info
    x0, y0, x1, y1 = bbox
    text_width = x1 - x0
    text_center = (x0 + x1) / 2
    page_center = page_width / 2
    left_margin = x0
    right_margin = page_width - x1
    
    # --- RULE 1: ISOLATED TEXT DETECTION ---
    if is_isolated_text(text, bbox, all_text_items):
        # Check if it's currently near center
        if abs(text_center - page_center) < page_width * 0.15:  # Within 15% of center
            return 'isolated_center'
        # Even if not centered, isolated headers should be centered
        elif is_header_like(text, line_text):
            return 'isolated_center'
    
    # --- RULE 2: TABLE/LIST DETECTION ---
    table_context = detect_table_context(text, bbox, all_text_items)
    if table_context:
        return table_context
    
    # --- RULE 3: NUMBERED/BULLETED LISTS ---
    if is_list_item(line_text):
        return 'table_left'  # Lists should shift right when longer
    
    # --- RULE 4: FORM FIELDS/LABELS ---
    if is_form_field(text, line_text, bbox, all_text_items):
        return 'table_left'  # Form fields shift right
    
    # --- RULE 5: DEFAULT BASED ON POSITION ---
    # If very close to left edge, it's probably table content
    if left_margin < 30:
        return 'table_left'
    
    # If very close to right edge, it's probably right-aligned content
    if right_margin < 30:
        return 'table_right'
    
    # Default: continuation text
    return 'continuation'


def is_isolated_text(text: str, bbox: tuple, all_text_items: List[Dict]) -> bool:
    """Check if text is isolated (has significant spacing around it)"""
    x0, y0, x1, y1 = bbox
    isolation_threshold = 20  # Minimum distance to be considered isolated
    
    # Check vertical isolation
    texts_above = [item for item in all_text_items 
                   if item['y'] < y0 - isolation_threshold and 
                   abs(item['x'] - x0) < 100]  # Same general horizontal area
    
    texts_below = [item for item in all_text_items 
                   if item['y'] > y1 + isolation_threshold and 
                   abs(item['x'] - x0) < 100]
    
    # Check horizontal isolation
    texts_left = [item for item in all_text_items 
                  if item['x'] < x0 - isolation_threshold and 
                  abs(item['y'] - y0) < 10]  # Same line
    
    texts_right = [item for item in all_text_items 
                   if item['x'] > x1 + isolation_threshold and 
                   abs(item['y'] - y0) < 10]
    
    # Text is isolated if it has space in at least 2 directions
    isolation_count = 0
    if not texts_above: isolation_count += 1
    if not texts_below: isolation_count += 1
    if not texts_left: isolation_count += 1
    if not texts_right: isolation_count += 1
    
    return isolation_count >= 2


def is_header_like(text: str, line_text: str) -> bool:
    """Check if text looks like a header or title"""
    # Header patterns
    header_patterns = [
        r'^[A-Z][A-Za-z\s]+$',  # Title Case or ALL CAPS
        r'.*(?:slip|reservation|ticket|details|payment|passenger).*',  # Header keywords
        r'^[A-Z\s\(\)]+$',  # ALL CAPS with spaces and parentheses
    ]
    
    for pattern in header_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    # Short phrases are often headers
    if len(text.split()) <= 4 and len(text) > 3:
        return True
    
    return False


def detect_table_context(text: str, bbox: tuple, all_text_items: List[Dict]) -> str:
    """Detect if text is part of a table structure"""
    x0, y0, x1, y1 = bbox
    
    # Find texts on the same horizontal line
    same_line_texts = [item for item in all_text_items 
                       if abs(item['y'] - y0) < 5 and item['x'] != x0]
    
    # If there are multiple items on the same line, it's likely tabular
    if len(same_line_texts) >= 2:
        # Determine position within the table
        texts_to_left = [item for item in same_line_texts if item['x'] < x0]
        texts_to_right = [item for item in same_line_texts if item['x'] > x1]
        
        if len(texts_to_left) == 0:
            return 'table_left'  # Leftmost column
        elif len(texts_to_right) == 0:
            return 'table_right'  # Rightmost column
        else:
            return 'table_left'  # Middle column, prefer left alignment
    
    # Check for vertical alignment (columns)
    vertical_aligned = [item for item in all_text_items 
                        if abs(item['x'] - x0) < 10 and abs(item['y'] - y0) > 10]
    
    if len(vertical_aligned) >= 2:
        return 'table_left'  # Part of a column
    
    return None


def is_list_item(line_text: str) -> bool:
    """Check if text is part of a numbered or bulleted list"""
    list_patterns = [
        r'^\s*\d+[\.\)]\s',          # 1. or 1)
        r'^\s*[A-Za-z][\.\)]\s',     # A. or a)
        r'^\s*[•\-\*\▪\◦]\s',        # Bullet points
        r'^\s*\([A-Za-z0-9]\)\s',    # (1) or (a)
        r'^\s*[IVX]+[\.\)]\s',       # Roman numerals
    ]
    
    for pattern in list_patterns:
        if re.search(pattern, line_text):
            return True
    
    return False


def is_form_field(text: str, line_text: str, bbox: tuple, all_text_items: List[Dict]) -> bool:
    """Check if text is a form field or label"""
    # Form field patterns
    form_patterns = [
        r'.*:$',  # Ends with colon (label)
        r'^\d+$',  # Just numbers
        r'^[A-Z]{2,}$',  # Short abbreviations
        r'.*\(\w+\).*',  # Text with abbreviations in parentheses
    ]
    
    for pattern in form_patterns:
        if re.search(pattern, text):
            return True
    
    # Check if followed by data on the same line
    x0, y0, x1, y1 = bbox
    texts_after = [item for item in all_text_items 
                   if item['x'] > x1 and abs(item['y'] - y0) < 5]
    
    if texts_after:
        # If there's text immediately after, this might be a label
        return True
    
    return False


def calculate_smart_position(text: str, old_text: str, context_type: str, 
                           original_bbox: tuple, page_width: float) -> tuple:
    """
    Calculate new position based on context type and text change.
    
    Returns: (new_x0, new_y0, new_x1, new_y1)
    """
    x0, y0, x1, y1 = original_bbox
    old_width = x1 - x0
    
    # Estimate new width (rough calculation)
    width_ratio = len(text) / len(old_text) if old_text else 1
    new_width = old_width * width_ratio
    
    if context_type == 'isolated_center':
        # Center the text on the page
        page_center = page_width / 2
        new_x0 = page_center - (new_width / 2)
        new_x1 = new_x0 + new_width
        return (new_x0, y0, new_x1, y1)
    
    elif context_type == 'table_left':
        # Keep left edge fixed, expand right
        return (x0, y0, x0 + new_width, y1)
    
    elif context_type == 'table_right':
        # Keep right edge fixed, expand left
        return (x1 - new_width, y0, x1, y1)
    
    elif context_type == 'continuation':
        # Keep left edge, expand naturally
        return (x0, y0, x0 + new_width, y1)
    
    # Default: keep original position
    return original_bbox


# Example usage function
def get_smart_alignment(text: str, old_text: str, line_text: str, bbox: tuple, 
                       page_width: float, all_text_items: List[Dict]) -> Dict:
    """
    Main function to get smart alignment for edited text.
    
    Returns:
        {
            'context_type': str,
            'new_bbox': tuple,
            'strategy': str,
            'reasoning': str
        }
    """
    context_type = detect_text_context(text, line_text, bbox, page_width, all_text_items)
    new_bbox = calculate_smart_position(text, old_text, context_type, bbox, page_width)
    
    reasoning_map = {
        'isolated_center': f"Text '{text}' is isolated → CENTER it",
        'table_left': f"Text '{text}' is in table/list → SHIFT RIGHT",
        'table_right': f"Text '{text}' is right-aligned → SHIFT LEFT", 
        'continuation': f"Text '{text}' is continuation → EXPAND RIGHT"
    }
    
    return {
        'context_type': context_type,
        'new_bbox': new_bbox,
        'strategy': context_type,
        'reasoning': reasoning_map.get(context_type, "Default positioning")
    }
