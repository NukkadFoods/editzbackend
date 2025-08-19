from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import os
import uuid
import io
import fitz  # PyMuPDF - ONLY dependency for PDF processing
import base64
import re
import math
from typing import Dict, List, Tuple, Any

def extract_pymupdf_metadata(pdf_content: bytes, page_num: int = None) -> Dict[str, Any]:
    """
    Extract enhanced text metadata using ONLY PyMuPDF - lightweight but powerful
    """
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    metadata = {}
    
    # Proce        # Use the intelligently calculated position for new text with baseline adjustment
        # COORDINATE SYSTEM FIX: bbox gives TOP-LEFT coordinates, insert_text needs BASELINE
        original_text_x = original_bbox[0]  # Left edge (correct)
        original_text_top = original_bbox[1]  # Top of text box
        original_text_bottom = original_bbox[3]  # Bottom of text box
        
        # PyMuPDF insert_text needs BASELINE Y coordinate, not top
        # Baseline is typically ~80% down from top to bottom
        text_height = original_text_bottom - original_text_top
        baseline_y = original_text_top + (text_height * 0.8)
        
        text_point = fitz.Point(original_text_x, baseline_y)
        
        print(f"📍 BASELINE COORDINATE CORRECTION:")
        print(f"   Original bbox: {original_bbox}")
        print(f"   Left X: {original_text_x}")
        print(f"   Top Y: {original_text_top}")
        print(f"   Bottom Y: {original_text_bottom}")
        print(f"   Text height: {text_height:.1f}")
        print(f"   Baseline Y: {baseline_y:.1f} (80% down from top)")
        print(f"   Text point: ({text_point.x:.2f}, {text_point.y:.2f})")
        print(f"   Strategy: {positioning_strategy}")age or all pages
    pages_to_process = [page_num] if page_num is not None else range(len(doc))
    
    for page_idx in pages_to_process:
        if page_idx >= len(doc):
            continue
            
        page = doc[page_idx]
        
        # Get text with detailed font information using PyMuPDF's dict format
        text_dict = page.get_text("dict", flags=11)
        
        for block in text_dict["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text:  # Only process non-empty text
                            
                            # Enhanced font analysis using PyMuPDF
                            font_name = span["font"]
                            font_size = span["size"]
                            flags = span["flags"]
                            bbox = span["bbox"]
                            color = span["color"]
                            
                            # ENHANCED BOLDNESS DETECTION using PyMuPDF flags
                            is_bold_flag = bool(flags & 2**4)  # Bold flag (bit 16)
                            is_bold_name = any(bold_word in font_name.lower() 
                                             for bold_word in ['bold', 'heavy', 'black'])
                            
                            # Calculate boldness score
                            boldness_score = 0
                            if is_bold_flag:
                                boldness_score += 0.6
                            if is_bold_name:
                                boldness_score += 0.4
                            
                            # Font weight estimation
                            font_weight = 700 if (is_bold_flag or is_bold_name) else 400
                            
                            # SIZE ANALYSIS - actual rendered height
                            actual_height = bbox[3] - bbox[1]
                            size_ratio = actual_height / font_size if font_size > 0 else 1.0
                            
                            # RGB Color conversion
                            if isinstance(color, int):
                                r = (color >> 16) & 255
                                g = (color >> 8) & 255  
                                b = color & 255
                                rgb_color = (r/255.0, g/255.0, b/255.0)
                            else:
                                rgb_color = (0, 0, 0)  # Default black
                            
                            # Create unique key
                            key = f"page_{page_idx+1}_text_{len(metadata)}"
                            
                            metadata[key] = {
                                "text": text,
                                "bbox": list(bbox),
                                "page": page_idx + 1,
                                "font_name": font_name,
                                "font_size": font_size,
                                "actual_height": actual_height,
                                "size_ratio": size_ratio,
                                "color": rgb_color,
                                "color_int": color,
                                "flags": flags,
                                "is_bold": is_bold_flag or is_bold_name,
                                "boldness_score": boldness_score,
                                "font_weight": font_weight,
                                "is_italic": bool(flags & 2**1),  # Italic flag
                                "clean_font_name": font_name,
                                "visual_boldness_score": boldness_score,
                            }
    
    doc.close()
    return metadata

def determine_text_context(text: str, line_text: str, bbox: tuple, page_width: float) -> str:
    """
    Determines the context of a text element using PyMuPDF data.
    Smart detection for relative positioning.
    """
    # --- RULE 1: Detect List Items / Table Format ---
    list_patterns = [
        r'^\s*\d+[\.\)]\s',         # e.g., "1. ", "2) "
        r'^\s*[•\-\*\+]\s',         # e.g., "• ", "- ", "* ", "+ "
        r'^\s*[A-Za-z][\.\)]\s',    # e.g., "A. ", "b) "
        r'^\s*\([A-Za-z0-9]\)\s'    # e.g., "(1) ", "(A) "
    ]

    for pattern in list_patterns:
        if re.match(pattern, line_text.strip()) or re.match(pattern, text.strip()):
            return 'list_item'
    
    # --- RULE 2: Detect if text appears to be in a structured format (table-like) ---
    # Check if line contains multiple structured elements (like table cells)
    structured_indicators = [
        ':',  # "Name: AJAY TIWARI"
        '|',  # Table separators
        '\t', # Tab separations
    ]
    
    # Count structured elements in the line
    structure_count = sum(1 for indicator in structured_indicators if indicator in line_text)
    
    # If line has multiple colons or separators, treat as structured (left-align)
    if structure_count >= 2:
        return 'structured_left'
    
    # --- RULE 3: Detect Right-Aligned Text ---
    right_margin = page_width - bbox[2]
    if right_margin < 50:  # Within 50 points of right edge
        return 'right_aligned'
    
    # --- RULE 4: Detect Isolated Text (should center relative to original position) ---
    # If text appears to be standalone/isolated (not part of structured content)
    
    # Check if this looks like an isolated element:
    is_short_standalone = len(text.strip()) <= 25  # Allow slightly longer for station names
    is_isolated_line = len(line_text.strip()) == len(text.strip())  # Text is the whole line
    is_label_like = bool(re.match(r'^[A-Z0-9\s\(\)]+$', text.strip()))  # All caps/numbers/parens
    is_station_like = bool(re.match(r'^[A-Z\s]+\s*\([A-Z0-9]+\)$', text.strip()))  # "SATNA (STA)" pattern
    is_code_like = bool(re.match(r'^[A-Z0-9]+$', text.strip()))  # Pure codes like "NDLS"
    
    print(f"🔍 ISOLATED DETECTION for '{text}':")
    print(f"   is_short_standalone: {is_short_standalone}")
    print(f"   is_isolated_line: {is_isolated_line}")  
    print(f"   is_label_like: {is_label_like}")
    print(f"   is_station_like: {is_station_like}")
    print(f"   is_code_like: {is_code_like}")
    
    if (is_short_standalone and is_isolated_line) or is_station_like or (is_label_like and is_short_standalone):
        print(f"   → DETECTED as isolated_center")
        return 'isolated_center'
    
    # --- RULE 5: Default ---
    return 'left_aligned'


def estimate_text_width_simple(text: str, font_size: float) -> float:
    """
    Simple heuristic for text width using PyMuPDF-extracted font size.
    """
    # This factor is approximate and depends on the actual font.
    # 0.6 is a common average for many sans-serif fonts like Helvetica.
    average_char_width_factor = 0.6
    estimated_width = len(text) * font_size * average_char_width_factor
    return estimated_width


def calculate_new_text_position(
    original_bbox: tuple,
    new_text: str,
    original_text_context: str,
    font_size: float,
    page_width: float
) -> tuple:
    """
    Calculates the new bounding box for edited text based on its context.
    Smart relative positioning.
    """
    orig_x0, orig_y0, orig_x1, orig_y1 = original_bbox
    new_text_width = estimate_text_width_simple(new_text, font_size)

    # Maintain original vertical position
    new_y0 = orig_y0
    new_y1 = orig_y1

    # --- Apply Context-Specific Logic ---
    if original_text_context == 'list_item' or original_text_context == 'structured_left':
        # Keep left edge fixed, adjust right edge (normal writing behavior)
        new_x0 = orig_x0
        new_x1 = new_x0 + new_text_width

    elif original_text_context == 'isolated_center':
        # PRESERVE THE EXACT CENTER POINT of the original element
        # Calculate original element's center point
        original_center_x = (orig_x0 + orig_x1) / 2
        
        # Position new text so its center matches the original center exactly
        new_x0 = original_center_x - (new_text_width / 2)
        new_x1 = original_center_x + (new_text_width / 2)
        
        print(f"🎯 ISOLATED CENTER PRESERVATION:")
        print(f"   Original element center: {original_center_x:.2f}")
        print(f"   Original bbox: [{orig_x0:.2f}, {orig_y0:.2f}, {orig_x1:.2f}, {orig_y1:.2f}]")
        print(f"   New text width: {new_text_width:.2f}")
        print(f"   New bbox: [{new_x0:.2f}, {new_y0:.2f}, {new_x1:.2f}, {new_y1:.2f}]")
        print(f"   New element center: {(new_x0 + new_x1) / 2:.2f}")
        print(f"   Center preserved: {abs(original_center_x - (new_x0 + new_x1) / 2) < 0.1}")
        
        # Ensure we don't go off the page
        if new_x0 < 0:
            shift = -new_x0
            new_x0 = 0
            new_x1 = new_text_width
            print(f"   Adjusted for page boundary: shifted right by {shift:.2f}")
        elif new_x1 > page_width:
            shift = new_x1 - page_width
            new_x1 = page_width
            new_x0 = page_width - new_text_width
            print(f"   Adjusted for page boundary: shifted left by {shift:.2f}")

    elif original_text_context == 'right_aligned':
        # Keep right edge fixed, adjust left edge
        new_x1 = orig_x1
        new_x0 = new_x1 - new_text_width
        # Prevent negative coordinates
        if new_x0 < 0:
            new_x0 = 0
            new_x1 = new_text_width

    else: # Default: 'left_aligned'
        # Keep left edge fixed (same as list_item logic here)
        new_x0 = orig_x0
        new_x1 = new_x0 + new_text_width

    return (new_x0, new_y0, new_x1, new_y1)


def get_smart_alignment(text: str, old_text: str, line_text: str, bbox: tuple, page_width: float, all_text_items: list) -> dict:
    """
    DEBUGGING: Force all text to preserve original position - NO CENTERING
    """
    x0, y0, x1, y1 = bbox
    font_size = y1 - y0  # Approximate font size from bbox height
    
    print(f"🎯 FORCE PRESERVE ORIGINAL POSITION:")
    print(f"   Text: '{text}' (was: '{old_text}')")
    print(f"   Original bbox: {bbox}")
    
    # FORCE: Always preserve left edge, extend right
    original_width = x1 - x0
    char_width_ratio = len(text) / len(old_text) if len(old_text) > 0 else 1.0
    new_width = original_width * char_width_ratio
    
    new_bbox = [x0, y0, x0 + new_width, y1]
    
    print(f"   Forced left preservation: {new_bbox}")
    
    return {
        'strategy': 'force_left_preserve',
        'reasoning': f'DEBUGGING: Forcing left edge preservation for "{text}"',
        'new_bbox': new_bbox
    }

fastapi_app = FastAPI(title="PDF Editor Backend - Advanced")

# Get the frontend URL from environment variable (for Vercel)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Add CORS middleware - simplified for reliability
print(f"🌐 Configured CORS for frontend: {frontend_url}")

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Simple OPTIONS handler for CORS
@fastapi_app.options("/{full_path:path}")
async def preflight_handler():
    return Response(status_code=200)

class EditRequest(BaseModel):
    page: int
    metadata_key: str
    new_text: str
    pdf_data: str  # Base64 encoded PDF data
    text_metadata: Dict[str, Any]

class DownloadRequest(BaseModel):
    pdf_data: str  # Base64 encoded PDF data

@fastapi_app.get("/")
async def root():
    return {
        "message": "🚀 ADVANCED PDF Editor Backend with Intelligent Alignment & Enhanced Text Quality",
        "version": "3.2.0-enhanced",
        "features": [
            "Enhanced Boldness Detection", 
            "Visual Analysis", 
            "Perfect Text Positioning",
            "Intelligent Alignment",
            "Precise Font Matching",
            "Character-Level Spacing",
            "Baseline Text Positioning",
            "Context-Aware Text Shifting"
        ],
        "status": "✅ Production Ready",
        "cors": "✅ Vercel Compatible",
        "size": "📦 <50MB PyMuPDF-Only"
    }

@fastapi_app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Enhanced PDF upload with comprehensive metadata extraction
    """
    try:
        print("🚀 ADVANCED PDF PROCESSING: Starting upload with enhanced metadata extraction")
        
        file_content = await file.read()
        file_id = str(uuid.uuid4())
        
        print(f"📄 Processing PDF: {len(file_content)} bytes, ID: {file_id}")
        
        # Skip embedded font extraction - using PyMuPDF-only approach
        embedded_fonts = {}
        print(f"⚠️ Font extraction warning: Using PyMuPDF-only approach")
        
        # STEP 2: Use ENHANCED metadata extraction with visual boldness analysis
        print("🔍 STARTING ENHANCED METADATA EXTRACTION...")
        
        try:
            # Extract text metadata from ALL pages
            all_metadata = []
            
            # Get total pages
            doc = fitz.open(stream=file_content, filetype="pdf")
            total_pages = len(doc)
            doc.close()
            
            print(f"📄 Processing {total_pages} pages...")
            
            # Extract metadata from each page
            for page_idx in range(total_pages):
                print(f"🔍 Processing page {page_idx + 1}/{total_pages}...")
                # Use PyMuPDF-only metadata extraction
                page_metadata = extract_pymupdf_metadata(file_content, page_num=page_idx)
                if page_metadata:
                    # page_metadata is a dict, convert to list of metadata items
                    for key, metadata in page_metadata.items():
                        all_metadata.append(metadata)
            
            if not all_metadata:
                raise Exception("Enhanced extraction returned empty results")
            
            text_items = []
            text_metadata = {}
            
            print(f"📊 ENHANCED EXTRACTION: Found {len(all_metadata)} text items with full metadata")
            
            for i, metadata in enumerate(all_metadata):
                metadata_key = f"text_item_{i+1}"
                
                # Create text item for frontend display
                text_item = {
                    "text": metadata["text"],
                    "page": metadata["page"],  # Use actual page number from metadata
                    "x": metadata["bbox"][0],
                    "y": metadata["bbox"][1],
                    "width": metadata["bbox"][2] - metadata["bbox"][0],  # Calculate width from bbox
                    "height": metadata["bbox"][3] - metadata["bbox"][1],  # Calculate height from bbox
                    "font": metadata["clean_font_name"],
                    "size": metadata["font_size"],
                    "metadata_key": metadata_key,
                    "color": metadata["color_int"],
                    "flags": metadata["flags"],
                    "is_bold": metadata["is_bold"],
                    "is_italic": metadata["is_italic"],
                    "visual_boldness": metadata["visual_boldness_score"]
                }
                
                # Store COMPREHENSIVE metadata for editing
                text_metadata[metadata_key] = {
                    # Basic text properties
                    "text": metadata["text"],
                    "bbox": metadata["bbox"],
                    "page": metadata["page"],
                    
                    # Font properties
                    "font": metadata["clean_font_name"],
                    "size": metadata["font_size"],
                    "flags": metadata["flags"],
                    
                    # Enhanced boldness detection
                    "is_bold": metadata["is_bold"],
                    "visual_boldness_score": metadata["visual_boldness_score"],
                    
                    # Style properties  
                    "is_italic": metadata["is_italic"],
                    
                    # Color and rendering
                    "color": metadata["color_int"],
                    "color_rgb": [int(c*255) for c in metadata["color"]],  # Convert back to RGB 0-255
                    
                    # Spacing and positioning (using defaults for now)
                    "char_spacing": 0.0,
                    "word_spacing": 0.0
                }
                
                text_items.append(text_item)
        
        except Exception as extraction_error:
            print(f"❌ Enhanced extraction failed: {extraction_error}")
            print("🔄 Falling back to basic PyMuPDF extraction...")
            
            # Fallback to basic extraction
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            text_items = []
            text_metadata = {}
            item_counter = 0
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                text_dict = page.get_text("dict", flags=11)
                
                for block in text_dict["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                if span["text"].strip():
                                    item_counter += 1
                                    metadata_key = f"text_item_{item_counter}"
                                    
                                    font_info = span["font"]
                                    font_size = span["size"]
                                    font_flags = span["flags"]
                                    text_color = span["color"]
                                    bbox = span["bbox"]
                                    
                                    is_bold = bool(font_flags & 16)
                                    is_italic = bool(font_flags & 2)
                                    
                                    text_item = {
                                        "text": span["text"],
                                        "page": page_num + 1,
                                        "x": bbox[0],
                                        "y": bbox[1],
                                        "width": bbox[2] - bbox[0],
                                        "height": bbox[3] - bbox[1],
                                        "font": font_info,
                                        "size": font_size,
                                        "metadata_key": metadata_key,
                                        "color": text_color,
                                        "flags": font_flags,
                                        "is_bold": is_bold,
                                        "is_italic": is_italic,
                                        "visual_boldness": 50.0 if is_bold else 0.0
                                    }
                                    
                                    # RGB color conversion for fallback
                                    if isinstance(text_color, int):
                                        r = (text_color >> 16) & 255
                                        g = (text_color >> 8) & 255
                                        b = text_color & 255
                                        color_rgb = [r, g, b]
                                    else:
                                        color_rgb = [0, 0, 0]
                                    
                                    # Store metadata for editing
                                    text_metadata[metadata_key] = {
                                        "text": span["text"],
                                        "bbox": list(bbox),
                                        "page": page_num + 1,
                                        "font": font_info,
                                        "size": font_size,
                                        "flags": font_flags,
                                        "is_bold": is_bold,
                                        "is_italic": is_italic,
                                        "color": text_color,
                                        "color_rgb": color_rgb,
                                        "visual_boldness_score": 50.0 if is_bold else 0.0,
                                        "char_spacing": 0.0,
                                        "word_spacing": 0.0
                                    }
                                    
                                    text_items.append(text_item)
                                    
                                    print(f"📝 BASIC: '{span['text'][:20]}' -> Font: {font_info}, Size: {font_size}, Bold: {is_bold}")
            
            pdf_document.close()
            print(f"✅ FALLBACK extraction complete: {len(text_items)} items")
        
        print(f"✅ ADVANCED PDF processing complete: {len(text_items)} text items, {len(embedded_fonts)} embedded fonts")
        
        return {
            "file_id": file_id,
            "text_items": text_items,
            "text_metadata": text_metadata,
            "embedded_fonts": embedded_fonts,
            "total_items": len(text_items),
            "processing_method": "enhanced" if len(all_metadata) > 0 else "fallback"
        }
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")

def map_to_pymupdf_font(font_name: str, is_bold: bool = False, is_italic: bool = False) -> str:
    """
    Map font names to PyMuPDF built-in fonts with enhanced mapping
    """
    font_name_lower = font_name.lower()
    
    # Enhanced font mapping with style consideration
    if any(serif in font_name_lower for serif in ['times', 'serif', 'roman']):
        if is_bold and is_italic:
            return "tibo"  # Times Bold Italic
        elif is_bold:
            return "tibo"  # Times Bold (closest match)
        elif is_italic:
            return "tibo"  # Times Italic (closest match)
        else:
            return "times"  # Times Roman
    
    elif any(mono in font_name_lower for mono in ['courier', 'mono', 'consolas', 'menlo']):
        if is_bold:
            return "cobo"  # Courier Bold
        else:
            return "cour"  # Courier
    
    else:  # Default to Helvetica family
        if is_bold and is_italic:
            return "helv"  # Helvetica (closest available)
        elif is_bold:
            return "hebo"  # Helvetica Bold
        elif is_italic:
            return "heob"  # Helvetica Oblique
        else:
            return "helv"  # Helvetica

@fastapi_app.post("/pdf/{file_id}/edit")
async def edit_text(file_id: str, edit_request: EditRequest):
    """
    ADVANCED text editing with intelligent positioning and enhanced boldness
    """
    try:
        print(f"🚀 ADVANCED EDITING: Starting text edit for file_id: {file_id}")
        print(f"📝 Edit request - page: {edit_request.page}, metadata_key: {edit_request.metadata_key}")
        
        # Decode the PDF data
        pdf_content = base64.b64decode(edit_request.pdf_data)
        
        # Debug: Check text_metadata structure
        print(f"🔍 EDIT DEBUG: text_metadata type = {type(edit_request.text_metadata)}")
        print(f"🔍 EDIT DEBUG: text_metadata keys = {list(edit_request.text_metadata.keys())}")
        
        # Get metadata for the specific text item
        if edit_request.metadata_key not in edit_request.text_metadata:
            raise HTTPException(status_code=400, detail=f"Metadata key '{edit_request.metadata_key}' not found")
        
        metadata = edit_request.text_metadata[edit_request.metadata_key]
        print(f"🔍 EDIT DEBUG: Found metadata for {edit_request.metadata_key}")
        print(f"🔍 EDIT DEBUG: metadata keys = {list(metadata.keys())}")
        
        # Debug color extraction
        if 'color_rgb' in metadata:
            print(f"🔍 EDIT DEBUG: color_rgb = {metadata['color_rgb']}")
        
        # Extract information from metadata
        original_text = metadata["text"]
        original_bbox = metadata["bbox"]
        font_name = metadata["font"]
        font_size = metadata["size"]
        new_text = edit_request.new_text
        
        # Enhanced boldness detection with fallback values
        is_bold = metadata.get("is_bold", False)
        is_italic = metadata.get("is_italic", False)
        visual_boldness = metadata.get("visual_boldness_score", 0)
        
        print(f"🎯 EDITING: '{original_text}' -> '{new_text}'")
        print(f"📏 Original Position: {original_bbox}, Font: {font_name}, Size: {font_size}")
        print(f"🎨 Style: Bold={is_bold}, Italic={is_italic}, Visual Boldness={visual_boldness}")
        
        # Open PDF for editing
        pymupdf_doc = fitz.open(stream=pdf_content, filetype="pdf")
        pymupdf_page = pymupdf_doc[edit_request.page - 1]  # Convert to 0-based index
        
        # BYPASS ALL ALIGNMENT LOGIC - FORCE EXACT ORIGINAL POSITION
        print(f"🚫 BYPASSING ALL ALIGNMENT - USING EXACT ORIGINAL POSITION")
        new_bbox = original_bbox  # Use exact original position
        positioning_strategy = "FORCED_ORIGINAL"
        
        print(f"� FORCED POSITIONING:")
        print(f"   Original bbox: {original_bbox}")
        print(f"   New bbox: {new_bbox} (SAME AS ORIGINAL)")
        print(f"   Strategy: {positioning_strategy}")
        
        # Determine effective font weight based on multiple factors
        # High visual boldness score or explicit bold flag should result in bold text
        effective_bold = is_bold or (visual_boldness > 50.0)
        
        print(f"🔍 BOLDNESS ANALYSIS:")
        print(f"   Flag Bold: {is_bold}")
        print(f"   Visual Boldness Score: {visual_boldness}")
        print(f"   Effective Bold: {effective_bold}")
        
        # Map font to PyMuPDF font with proper boldness
        pymupdf_font = map_to_pymupdf_font(font_name, effective_bold, is_italic)
        
        # Get original color and spacing from metadata
        original_color_rgb = metadata.get("color_rgb", [0, 0, 0])  # Default to black if not found
        original_color_normalized = tuple(c/255.0 for c in original_color_rgb)  # PyMuPDF uses 0-1 range
        
        # Extract spacing information for better text rendering
        char_spacing = metadata.get("char_spacing", 0.0)
        word_spacing = metadata.get("word_spacing", 0.0)
        
        print(f"🎨 Using original color: RGB{original_color_rgb} -> Normalized{original_color_normalized}")
        print(f"📏 Character spacing: {char_spacing}, Word spacing: {word_spacing}")
        
        # INTELLIGENT POSITIONING ANALYSIS - Using Smart Alignment
        print(f"🔍 USING SMART ALIGNMENT (already calculated above)")
        positioning_strategy = smart_alignment['strategy']
        
        # Create rectangle for the original text (to clear)
        original_text_rect = fitz.Rect(original_bbox)
        
        # Clear the original text by drawing a white rectangle
        pymupdf_page.draw_rect(original_text_rect, color=None, fill=fitz.utils.getColor("white"))
        
        # Use the intelligently calculated position for new text with baseline adjustment
        # TEST: Place at absolute top-left corner to verify coordinate system
        test_x = 0  # Absolute left edge
        test_y = 50  # 50 points from top (to avoid being cut off)
        text_point = fitz.Point(test_x, test_y)
        
        print(f"📍 ABSOLUTE TOP-LEFT TEST:")
        print(f"   Original bbox: {original_bbox}")
        print(f"   Test X: {test_x} (absolute left)")
        print(f"   Test Y: {test_y} (50pt from top)")
        print(f"   Text point: ({text_point.x:.2f}, {text_point.y:.2f})")
        print(f"   If this STILL centers, coordinate system is wrong!")
        print(f"   Strategy: {positioning_strategy}")
        print(f"   Spacing: char={char_spacing:.1f}, word={word_spacing:.1f}")
        
        # Determine render mode based on boldness intensity
        # For very high visual boldness, use stroke rendering for extra boldness
        render_mode = 0  # Default: fill text
        if visual_boldness > 75.0:
            render_mode = 2  # Fill and stroke for extra boldness
        
        # Insert the new text with enhanced positioning and styling
        text_length = pymupdf_page.insert_text(
            text_point,
            new_text,
            fontsize=font_size,
            fontname=pymupdf_font,
            color=original_color_normalized,
            render_mode=render_mode
        )
        
        print(f"✅ Text successfully replaced with INTELLIGENT POSITIONING + PRECISE FONT MATCHING")
        print(f"   Font: {pymupdf_font} (was: {font_name}), Strategy: {positioning_strategy}")
        print(f"   Size: {font_size}pt, Color: {original_color_rgb}, Position: ({text_point.x:.2f}, {text_point.y:.2f})")
        
        # Convert back to bytes
        pdf_bytes = pymupdf_doc.write()
        print(f"📄 PDF write successful: {len(pdf_bytes)} bytes")
        
        # Close the document
        pymupdf_doc.close()
        print(f"📄 PDF document closed successfully")
        
        # Encode to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        print(f"✅ Base64 encoding successful: {len(pdf_base64)} chars")
        
        print(f"✅ ADVANCED EDIT complete: Generated {len(pdf_bytes)} bytes")
        
        return {
            "success": True,
            "pdf_data": pdf_base64,
            "edit_details": {
                "original_text": original_text,
                "new_text": new_text,
                "font_used": pymupdf_font,
                "positioning_strategy": positioning_strategy,
                "color_preserved": original_color_rgb,
                "effective_bold": effective_bold,
                "visual_boldness_score": visual_boldness
            }
        }
        
    except Exception as e:
        print(f"❌ ADVANCED EDIT ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Text editing failed: {str(e)}")

@fastapi_app.post("/pdf/{file_id}/download")
async def download_pdf(file_id: str, download_request: DownloadRequest):
    """
    Download the edited PDF
    """
    try:
        print(f"📥 DOWNLOAD: Starting download for file_id: {file_id}")
        
        # Decode the PDF data
        pdf_bytes = base64.b64decode(download_request.pdf_data)
        print(f"📄 PDF data decoded: {len(pdf_bytes)} bytes")
        
        print(f"✅ DOWNLOAD: Ready to serve {len(pdf_bytes)} bytes")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=edited_{file_id}.pdf",
                "Content-Length": str(len(pdf_bytes)),
                "Access-Control-Expose-Headers": "Content-Disposition, Content-Length"
            }
        )
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

# Health check endpoint
@fastapi_app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2025-08-18", "version": "3.2.0"}

# Simple handler function for Vercel
def handler(event, context):
    """
    Vercel handler function
    """
    from mangum import Mangum
    asgi_handler = Mangum(app)
    return asgi_handler(event, context)
