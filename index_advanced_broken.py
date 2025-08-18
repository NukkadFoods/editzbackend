from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import os
import uuid
    return {
        "status": "healthy",
        "service": "pdf-editor-backend-advanced",
        "cors_enabled": True,
        "vercel_ready": True
    }

class EditRequest(BaseModel):fitz  # PyMuPDF
import pdfplumber  # Better font extraction
import pikepdf  # Direct PDF content editing
from fontTools.ttLib import TTFont  # Font analysis
from text_context_analyzer import TextShiftingAnalyzer
from intelligent_text_shifter import IntelligentTextShifter
import base64
import re
import math
from typing import Dict, List, Tuple, Any
from enhanced_metadata import extract_complete_text_metadata, analyze_text_differences

def get_smart_alignment(text: str, old_text: str, line_text: str, bbox: tuple, page_width: float, all_text_items: list) -> dict:
    """
    Determine if text should be centered, left-aligned, or maintain tabular positioning
    """
    x0, y0, x1, y1 = bbox
    text_width = x1 - x0
    text_center_x = (x0 + x1) / 2
    page_center_x = page_width / 2
    
    # Check if it's a list item (should NOT be centered)
    list_patterns = [
        r'^\d+\.\s',           # "1. ", "2. "
        r'^\d+\)\s',           # "1) ", "2) "
        r'^[•\-\*]\s',         # bullet points
        r'^\([A-Za-z0-9]\)\s', # "(A) ", "(1) "
    ]
    
    is_list_item = any(re.match(pattern, line_text.strip()) for pattern in list_patterns)
    
    if is_list_item:
        # List items should expand to the right
        new_width = len(text) * (text_width / len(old_text)) if old_text else text_width
        return {
            'strategy': 'list_expand_right',
            'reasoning': 'Detected list item - expanding right',
            'new_bbox': [x0, y0, x0 + new_width, y1]
        }
    
    # ENHANCED: Check for station names and location codes
    station_patterns = [
        r'^[A-Z\s]+\s*\([A-Z]{2,4}\)$',  # "SATNA (STA)", "NEW DELHI (NDLS)"
        r'^[A-Z]{2,4}\s*\([A-Z]{2,4}\)$', # "STA (SATNA)"
        r'^\w+\s*\([\w\s]+\)$',          # Generic "WORD (CODE)" pattern
    ]
    
    is_station = any(re.match(pattern, text.strip().upper()) for pattern in station_patterns)
    
    # DEBUG: Add detailed station detection logging
    print(f"🚉 STATION DETECTION DEBUG:")
    print(f"   Text: '{text}' -> Upper: '{text.strip().upper()}'")
    print(f"   Testing patterns:")
    for i, pattern in enumerate(station_patterns):
        match_result = re.match(pattern, text.strip().upper())
        print(f"   Pattern {i+1}: {pattern} -> {'✅ MATCH' if match_result else '❌ No match'}")
    print(f"   Is Station: {is_station}")
    
    # Check if text is near center (increased threshold for stations)
    distance_from_center = abs(text_center_x - page_center_x)
    is_near_center = distance_from_center < 60  # Increased from 30 to 60
    
    # Check if it's in the left third of the page (likely left-aligned)
    is_left_positioned = x0 < (page_width / 3)
    
    # Check if text appears to be in a column structure
    same_line_items = [item for item in all_text_items 
                      if abs(item['y'] - y0) < 5 and item['text'].strip()]
    
    is_tabular = len(same_line_items) > 2
    
    # ENHANCED LOGIC: Station names should maintain their center position
    if is_station:
        new_width = len(text) * (text_width / len(old_text)) if old_text else text_width
        # Keep the same center position as original text
        original_center_x = (x0 + x1) / 2
        new_x0 = original_center_x - (new_width / 2)
        return {
            'strategy': 'center_station',
            'reasoning': f'Station name detected: "{text}" - maintaining center position',
            'new_bbox': [new_x0, y0, new_x0 + new_width, y1]
        }
    
    # If text is near center and not clearly tabular, maintain center position
    elif is_near_center and not is_tabular:
        new_width = len(text) * (text_width / len(old_text)) if old_text else text_width
        # Keep the same center position as original text
        original_center_x = (x0 + x1) / 2
        new_x0 = original_center_x - (new_width / 2)
        return {
            'strategy': 'center_text',
            'reasoning': f'Near center (distance: {distance_from_center:.1f}) - maintaining center position',
            'new_bbox': [new_x0, y0, new_x0 + new_width, y1]
        }
    
    elif is_tabular and not is_left_positioned:
        # Tabular data should maintain column alignment
        new_width = len(text) * (text_width / len(old_text)) if old_text else text_width
        return {
            'strategy': 'maintain_column',
            'reasoning': 'Tabular layout - maintaining column',
            'new_bbox': [x0, y0, x0 + new_width, y1]
        }
    
    else:
        # Default: expand right for left-aligned text
        new_width = len(text) * (text_width / len(old_text)) if old_text else text_width
        return {
            'strategy': 'expand_right',
            'reasoning': f'Left positioned (x: {x0:.1f}) - expanding right',
            'new_bbox': [x0, y0, x0 + new_width, y1]
        }

app = FastAPI(title="PDF Editor Backend - Advanced")

# Enhanced CORS configuration for dynamic Vercel URLs
def is_allowed_origin(origin: str) -> bool:
    """Check if origin is allowed - supports dynamic Vercel URLs"""
    allowed_patterns = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    
    # Check exact matches first
    if origin in allowed_patterns:
        return True
    
    # Check Vercel patterns
    vercel_patterns = [
        r"^https://[a-zA-Z0-9\-]+\.vercel\.app$",  # Basic vercel apps
        r"^https://[a-zA-Z0-9\-]+-[a-zA-Z0-9\-]+-[a-zA-Z0-9\-]+\.vercel\.app$",  # Branch deployments
        r"^https://[a-zA-Z0-9\-]+-git-[a-zA-Z0-9\-]+-[a-zA-Z0-9\-]+\.vercel\.app$",  # Git branch deployments
        r"^https://[a-zA-Z0-9\-]+\-[a-zA-Z0-9]{8,}\-[a-zA-Z0-9\-]+\.vercel\.app$",  # Preview deployments
    ]
    
    for pattern in vercel_patterns:
        if re.match(pattern, origin):
            return True
    
    return False

# Add CORS middleware with dynamic origin checking
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https://.*\.vercel\.app$",  # Allow any Vercel domain
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

class EditRequest(BaseModel):
    page: int
    metadata_key: str
    new_text: str
    pdf_data: str  # Base64 encoded PDF data
    text_metadata: Dict[str, Any]

class DownloadRequest(BaseModel):
    pdf_data: str  # Base64 encoded PDF data

@app.get("/")
async def root():
    return {
        "message": "🚀 ADVANCED PDF Editor Backend with Intelligent Alignment & Enhanced Text Quality",
        "version": "3.3.0-universal-cors",
        "features": [
            "Enhanced Boldness Detection", 
            "Visual Analysis", 
            "Perfect Text Positioning",
            "Intelligent Alignment",
            "Multi-page Processing",
            "Universal CORS Support",
            "Dynamic Vercel URL Support"
        ],
        "cors_info": {
            "supports_vercel": True,
            "supports_localhost": True,
            "example_allowed_urls": [
                "https://editz-mv74cnjca-ajay-s-projects-7337fb6b.vercel.app",
                "https://your-app-name.vercel.app", 
                "https://your-app-git-main-username.vercel.app",
                "http://localhost:3000"
            ]
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment verification"""
    return {
        "status": "healthy",
        "service": "pdf-editor-backend-advanced",
        "cors_enabled": True,
        "vercel_ready": True
    }
        "capabilities": {
            "text_editing": "Advanced with intelligent positioning",
            "font_matching": "Precise with enhanced fallbacks",
            "color_preservation": "Perfect RGB accuracy",
            "boldness_detection": "Multi-factor analysis",
            "alignment": "Context-aware smart positioning",
            "spacing": "Character and word-level precision"
        }
    }

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """ADVANCED PDF processing with enhanced metadata extraction and visual boldness analysis"""
    try:
        print("🚀 ADVANCED PDF PROCESSING: Starting upload with enhanced metadata extraction")
        
        if not file.filename.lower().endswith('.pdf'):
            return {"success": False, "error": "Only PDF files are allowed", "filename": file.filename}
        
        file_content = await file.read()
        file_id = str(uuid.uuid4())
        
        print(f"📄 Processing PDF: {len(file_content)} bytes, ID: {file_id}")
        
        # STEP 1: Extract embedded fonts using pikepdf
        embedded_fonts = {}
        try:
            with pikepdf.open(io.BytesIO(file_content)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    if '/Resources' in page and '/Font' in page['/Resources']:
                        fonts = page['/Resources']['/Font']
                        for font_name, font_obj in fonts.items():
                            if '/FontDescriptor' in font_obj:
                                font_descriptor = font_obj['/FontDescriptor']
                                if '/FontFile2' in font_descriptor or '/FontFile' in font_descriptor:
                                    # Extract embedded font data
                                    font_data_key = '/FontFile2' if '/FontFile2' in font_descriptor else '/FontFile'
                                    font_stream = font_descriptor[font_data_key]
                                    embedded_fonts[str(font_name)] = {
                                        'font_data': bytes(font_stream),
                                        'font_name': str(font_obj.get('/BaseFont', font_name)),
                                        'is_embedded': True
                                    }
                                    print(f"🔤 Extracted embedded font: {font_name} -> {font_obj.get('/BaseFont', font_name)}")
        except Exception as e:
            print(f"⚠️ Font extraction warning: {e}")
        
        # STEP 2: Use ENHANCED metadata extraction with visual boldness analysis
        print("🔍 STARTING ENHANCED METADATA EXTRACTION...")
        
        try:
            # Extract text metadata from ALL pages
            all_metadata = []
            
            # Open PDF to get page count
            doc = fitz.open(stream=file_content, filetype="pdf")
            total_pages = len(doc)
            doc.close()
            
            print(f"📄 Processing {total_pages} pages...")
            
            # Extract metadata from each page
            for page_idx in range(total_pages):
                print(f"🔍 Processing page {page_idx + 1}/{total_pages}...")
                page_metadata = extract_complete_text_metadata(file_content, page_num=page_idx)
                if page_metadata:
                    all_metadata.extend(page_metadata)
            
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
                    "width": metadata["text_width"],
                    "height": metadata["text_height"],
                    "font": metadata["clean_font_name"],
                    "size": metadata["font_size"],
                    "metadata_key": metadata_key,
                    "color": metadata["color_int"],
                    "flags": metadata["font_flags"],
                    "is_bold": metadata["is_bold_final"],
                    "is_italic": metadata["is_italic_final"],
                    "visual_boldness": metadata["visual_boldness_score"]
                }
                
                # Store COMPREHENSIVE metadata for editing
                text_metadata[metadata_key] = {
                    # Basic text properties
                    "text": metadata["text"],
                    "bbox": metadata["bbox"],
                    "origin": metadata["origin"],
                    "page": metadata["page"],  # Use actual page number from metadata
                    
                    # Font properties
                    "font": metadata["clean_font_name"],
                    "raw_font_name": metadata["raw_font_name"],
                    "size": metadata["font_size"],
                    "font_flags": metadata["font_flags"],
                    
                    # Enhanced boldness detection
                    "is_bold": metadata["is_bold_final"],
                    "is_bold_flag": metadata["is_bold_flag"],
                    "is_bold_name": metadata["is_bold_name"],
                    "visual_boldness_score": metadata["visual_boldness_score"],
                    
                    # Style properties
                    "is_italic": metadata["is_italic_final"],
                    "is_light": metadata["is_light"],
                    "is_medium": metadata["is_medium"],
                    "is_serif": metadata["is_serif"],
                    "is_monospace": metadata["is_monospace"],
                    
                    # Color and rendering
                    "color": metadata["color_int"],
                    "color_rgb": metadata["color_rgb"],
                    "render_mode": metadata["render_mode"],
                    "underline": metadata["underline"],
                    "strikeout": metadata["strikeout"],
                    
                    # Spacing and positioning
                    "char_spacing": metadata["char_spacing"],
                    "word_spacing": metadata["word_spacing"],
                    "avg_char_width": metadata["avg_char_width"],
                    
                    # Transform properties
                    "transform_matrix": metadata["transform_matrix"],
                    "rotation_degrees": metadata["rotation_degrees"],
                    "scale_x": metadata["scale_x"],
                    "scale_y": metadata["scale_y"],
                    
                    # Character analysis
                    "char_count": metadata["char_count"],
                    "text_width": metadata["text_width"],
                    "text_height": metadata["text_height"]
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
                                        "visual_boldness": 0.0
                                    }
                                    
                                    text_metadata[metadata_key] = {
                                        "text": span["text"],
                                        "bbox": list(bbox),
                                        "font": font_info,
                                        "size": font_size,
                                        "color": text_color,
                                        "flags": font_flags,
                                        "page": page_num + 1,
                                        "is_bold": is_bold,
                                        "is_italic": is_italic
                                    }
                                    
                                    text_items.append(text_item)
                                    print(f"📝 BASIC: '{span['text'][:20]}' -> Font: {font_info}, Size: {font_size}, Bold: {is_bold}")
            
            pdf_document.close()
            print(f"✅ FALLBACK extraction complete: {len(text_items)} items")
        
        # Encode original PDF as base64 for frontend storage
        pdf_data_base64 = base64.b64encode(file_content).decode('utf-8')
        
        response = {
            "success": True,
            "fileId": file_id,
            "filename": file.filename,
            "textItems": text_items,
            "pdfData": pdf_data_base64,
            "textMetadata": text_metadata,
            "backendVersion": "ADVANCED_ENHANCED_METADATA_V4",
            "extractedItems": len(text_items),
            "embeddedFonts": len(embedded_fonts)
        }
        
        print(f"✅ ADVANCED PDF processing complete: {len(text_items)} text items, {len(embedded_fonts)} embedded fonts")
        return response
        
    except Exception as e:
        print(f"❌ ADVANCED PDF ERROR: {e}")
        return {"success": False, "error": str(e), "filename": file.filename if file else "unknown"}

def map_to_pymupdf_font(font_name: str, is_bold: bool, is_italic: bool) -> str:
    """Map font names to PyMuPDF fonts with enhanced precision and better matching"""
    font_lower = font_name.lower()
    
    # Enhanced font mapping with better fallbacks
    if any(name in font_lower for name in ['calibri']):
        # Calibri is very common in modern PDFs
        if is_bold and is_italic:
            return "hebo"  # Helvetica Bold as best substitute
        elif is_bold:
            return "hebo"  # Helvetica Bold
        elif is_italic:
            return "heit"  # Helvetica Italic
        else:
            return "helv"  # Regular Helvetica (closest to Calibri)
    elif any(name in font_lower for name in ['arial', 'helvetica']):
        if is_bold and is_italic:
            return "hebo"  # Use bold as primary
        elif is_bold:
            return "hebo"  # Helvetica Bold
        elif is_italic:
            return "heit"  # Helvetica Italic
        else:
            return "helv"  # Regular Helvetica
    elif any(name in font_lower for name in ['times', 'roman']):
        if is_bold and is_italic:
            return "tibo"  # Use bold as primary
        elif is_bold:
            return "tibo"  # Times Bold
        elif is_italic:
            return "tiit"  # Times Italic
        else:
            return "tiro"  # Times Roman
    elif any(name in font_lower for name in ['courier', 'mono']):
        if is_bold:
            return "cobo"  # Courier Bold
        else:
            return "cour"  # Regular Courier
    else:
        # Default mapping with better font selection
        if is_bold:
            return "hebo"  # Default to Helvetica Bold
        elif is_italic:
            return "heit"  # Default to Helvetica Italic
        else:
            return "helv"  # Default to Helvetica
            return "helv"  # Default to Helvetica

@app.post("/analyze-pdf")
async def analyze_pdf_boldness(file: UploadFile = File(...)):
    """DEBUG: Analyze PDF text with enhanced boldness detection"""
    try:
        if not file.filename.lower().endswith('.pdf'):
            return {"success": False, "error": "Only PDF files are allowed"}
        
        file_content = await file.read()
        
        # Run comprehensive analysis
        metadata_list = analyze_text_differences(file_content, page_num=0)
        
        # Summary statistics
        total_items = len(metadata_list)
        bold_flag_count = sum(1 for item in metadata_list if item['is_bold_flag'])
        bold_name_count = sum(1 for item in metadata_list if item['is_bold_name'])
        bold_final_count = sum(1 for item in metadata_list if item['is_bold_final'])
        high_visual_bold_count = sum(1 for item in metadata_list if item['visual_boldness_score'] > 2.0)
        
        return {
            "success": True,
            "total_text_items": total_items,
            "bold_detection_summary": {
                "bold_by_flag": bold_flag_count,
                "bold_by_name": bold_name_count,
                "bold_final_determination": bold_final_count,
                "high_visual_boldness": high_visual_bold_count
            },
            "detailed_analysis": metadata_list[:20],  # First 20 items for debugging
            "visual_boldness_scores": [item['visual_boldness_score'] for item in metadata_list]
        }
    
    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        return {"success": False, "error": str(e)}

@app.post("/pdf/{file_id}/edit")
async def edit_text(file_id: str, edit_request: EditRequest):
    """ADVANCED PDF text editing using precise font matching and perfect positioning"""
    try:
        print(f"🚀 ADVANCED EDITING: Starting text edit for file_id: {file_id}")
        print(f"📝 Edit request - page: {edit_request.page}, metadata_key: {edit_request.metadata_key}")
        print(f"🔍 EDIT DEBUG: text_metadata type = {type(edit_request.text_metadata)}")
        print(f"🔍 EDIT DEBUG: text_metadata keys = {list(edit_request.text_metadata.keys()) if edit_request.text_metadata else 'None'}")
        
        # Decode PDF data from request
        try:
            pdf_content = base64.b64decode(edit_request.pdf_data)
        except Exception as e:
            print(f"❌ Failed to decode PDF data: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid PDF data")
        
        # Get the specific text metadata
        if edit_request.metadata_key not in edit_request.text_metadata:
            print(f"❌ Metadata key not found: {edit_request.metadata_key}")
            print(f"🔍 Available keys: {list(edit_request.text_metadata.keys())}")
            raise HTTPException(status_code=400, detail="Text metadata not found")
        
        metadata = edit_request.text_metadata[edit_request.metadata_key]
        print(f"🔍 EDIT DEBUG: Found metadata for {edit_request.metadata_key}")
        print(f"🔍 EDIT DEBUG: metadata keys = {list(metadata.keys()) if metadata else 'None'}")
        if 'color_rgb' in metadata:
            print(f"🔍 EDIT DEBUG: color_rgb = {metadata['color_rgb']}")
        new_text = edit_request.new_text
        
        # Open with PyMuPDF for text manipulation
        pymupdf_doc = fitz.open(stream=pdf_content, filetype="pdf")
        pymupdf_page = pymupdf_doc[edit_request.page - 1]
        
        # Extract enhanced metadata with precise font matching
        original_bbox = metadata["bbox"]
        font_name = metadata["font"]
        raw_font_size = metadata["size"]
        # Use exact font size from original text, not rounded
        font_size = float(raw_font_size)  # Preserve decimal precision
        is_bold = metadata.get("is_bold_final", False)
        is_italic = metadata.get("is_italic", False)
        visual_boldness = metadata.get("visual_boldness_score", 0.0)
        original_text = metadata["text"]
        
        print(f"🎯 EDITING: '{original_text}' -> '{new_text}'")
        print(f"📏 Original Position: {original_bbox}, Font: {font_name}, Size: {font_size}")
        print(f"🎨 Style: Bold={is_bold}, Italic={is_italic}, Visual Boldness={visual_boldness}")
        
        # 🧠 INTELLIGENT POSITIONING: Analyze text context and calculate optimal position
        print(f"🧠 ANALYZING TEXT CONTEXT...")
        try:
            analyzer = TextShiftingAnalyzer(pdf_content, edit_request.page - 1)
            text_context = analyzer.analyze_text_context(original_text, original_bbox)
            analyzer.close()
            
            print(f"📊 CONTEXT ANALYSIS:")
            print(f"   Alignment: {text_context['alignment']}")
            print(f"   List Item: {text_context['is_list_item']}")
            print(f"   Header: {text_context['is_header']}")
            print(f"   Justified: {text_context['is_justified']}")
            
            # USE NEW SMART ALIGNMENT SYSTEM
            # Get all text items for context (simplified for now)
            all_text_items = [{'x': original_bbox[0], 'y': original_bbox[1], 'text': original_text}]
            page_width = pymupdf_page.rect.width
            
            smart_alignment = get_smart_alignment(
                text=new_text,
                old_text=original_text, 
                line_text=original_text,  # Using original text as line text for now
                bbox=original_bbox,
                page_width=page_width,
                all_text_items=all_text_items
            )
            
            print(f"🎯 SMART ALIGNMENT STRATEGY: {smart_alignment['strategy']}")
            print(f"� REASONING: {smart_alignment['reasoning']}")
            print(f"📏 New Position: {smart_alignment['new_bbox']}")
            
            # Use the smart alignment result
            new_bbox = smart_alignment['new_bbox']
            positioning_strategy = smart_alignment['strategy']
            
        except Exception as e:
            print(f"⚠️  Intelligent positioning failed: {e}")
            print(f"🔄 Falling back to original position")
            new_bbox = original_bbox
            positioning_strategy = "fallback"
        
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
        original_color_rgb = metadata.get("color_rgb", (0, 0, 0))  # Default to black if not found
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
        text_baseline_y = new_bbox[3] - (font_size * 0.2)  # Adjust for font baseline
        text_point = fitz.Point(new_bbox[0], text_baseline_y)
        
        print(f"📍 ENHANCED TEXT PLACEMENT:")
        print(f"   Original bbox: {original_bbox}")
        print(f"   New bbox: {new_bbox}")
        print(f"   Text point: ({text_point.x:.2f}, {text_point.y:.2f})")
        print(f"   Baseline adjusted Y: {text_baseline_y:.2f}")
        print(f"   Font size: {font_size}")
        print(f"   Strategy: {positioning_strategy}")
        print(f"   Spacing: char={char_spacing:.1f}, word={word_spacing:.1f}")
        
        # Determine render mode based on boldness intensity
        # For very high visual boldness, use stroke rendering for extra boldness
        render_mode = 0  # Default: fill text
        stroke_width = 0.0
        
        if visual_boldness > 80.0:  # Very bold text
            render_mode = 2  # Fill and stroke for extra boldness
            stroke_width = 0.2
        elif effective_bold:
            render_mode = 0  # Just use bold font
        
        try:
            if render_mode == 2:  # Enhanced boldness with stroke
                pymupdf_page.insert_text(
                    text_point,
                    new_text,
                    fontname=pymupdf_font,
                    fontsize=font_size,
                    color=original_color_normalized,
                    render_mode=render_mode,
                    stroke_width=stroke_width
                )
                print(f"✅ Text successfully replaced with ENHANCED BOLDNESS + INTELLIGENT POSITIONING")
                print(f"   Font: {pymupdf_font}, Visual Boldness: {visual_boldness:.1f}, Strategy: {positioning_strategy}")
                print(f"   Position: ({text_point.x:.2f}, {text_point.y:.2f})")
            else:
                pymupdf_page.insert_text(
                    text_point,
                    new_text,
                    fontname=pymupdf_font,
                    fontsize=font_size,
                    color=original_color_normalized
                )
                print(f"✅ Text successfully replaced with INTELLIGENT POSITIONING + PRECISE FONT MATCHING")
                print(f"   Font: {pymupdf_font} (was: {font_name}), Strategy: {positioning_strategy}")
                print(f"   Size: {font_size}pt, Color: {original_color_rgb}, Position: ({text_point.x:.2f}, {text_point.y:.2f})")
        except Exception as font_error:
            print(f"⚠️ Font insertion failed with {pymupdf_font}: {font_error}")
            # Fallback to default font with all enhancements preserved
            fallback_font = "hebo" if effective_bold else "helv"
            pymupdf_page.insert_text(
                text_point,
                new_text,
                fontname=fallback_font,
                fontsize=font_size,
                color=original_color_normalized
            )
            print(f"✅ Text replaced using ENHANCED FALLBACK: {fallback_font}")
            print(f"   Strategy: {positioning_strategy}, Size: {font_size}pt, Position: ({text_point.x:.2f}, {text_point.y:.2f})")
        
        # Generate modified PDF with better error handling
        try:
            modified_pdf_bytes = pymupdf_doc.write()
            print(f"📄 PDF write successful: {len(modified_pdf_bytes)} bytes")
        except Exception as write_error:
            print(f"❌ PDF write failed: {write_error}")
            pymupdf_doc.close()
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {write_error}")
        finally:
            # Always close the document
            try:
                pymupdf_doc.close()
                print("📄 PDF document closed successfully")
            except:
                pass
        
        # Encode as base64 with validation
        try:
            modified_pdf_base64 = base64.b64encode(modified_pdf_bytes).decode('utf-8')
            print(f"✅ Base64 encoding successful: {len(modified_pdf_base64)} chars")
        except Exception as encode_error:
            print(f"❌ Base64 encoding failed: {encode_error}")
            raise HTTPException(status_code=500, detail=f"PDF encoding failed: {encode_error}")
        
        print(f"✅ ADVANCED EDIT complete: Generated {len(modified_pdf_bytes)} bytes")
        
        return {
            "success": True,
            "message": f"Text successfully edited: '{metadata['text']}' -> '{new_text}'",
            "modifiedPdfData": modified_pdf_base64,
            "editDetails": {
                "original_text": metadata['text'],
                "new_text": new_text,
                "font_used": pymupdf_font,
                "position": original_bbox,
                "font_size": font_size
            }
        }
        
    except Exception as e:
        print(f"❌ ADVANCED EDIT ERROR: {e}")
        return {"success": False, "error": str(e)}

@app.post("/pdf/{file_id}/download")
async def download_pdf(file_id: str, download_request: DownloadRequest):
    """Download the edited PDF with enhanced error handling"""
    try:
        print(f"📥 DOWNLOAD: Starting download for file_id: {file_id}")
        
        # Validate PDF data
        if not download_request.pdf_data:
            raise HTTPException(status_code=400, detail="No PDF data provided")
        
        # Decode PDF data with validation
        try:
            pdf_content = base64.b64decode(download_request.pdf_data)
            print(f"📄 PDF data decoded: {len(pdf_content)} bytes")
        except Exception as decode_error:
            print(f"❌ PDF decode failed: {decode_error}")
            raise HTTPException(status_code=400, detail=f"Invalid PDF data: {decode_error}")
        
        # Validate PDF content
        if len(pdf_content) < 100:  # PDF should be at least 100 bytes
            raise HTTPException(status_code=400, detail="PDF data too small")
        
        # Verify it's a valid PDF
        if not pdf_content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Invalid PDF format")
        
        print(f"✅ DOWNLOAD: Ready to serve {len(pdf_content)} bytes")
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=edited_{file_id}.pdf",
                "Content-Length": str(len(pdf_content))
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ DOWNLOAD ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.get("/pdf/{file_id}/pages/{page_num}/text")
async def get_page_text(file_id: str, page_num: int):
    """Get text items for a specific page"""
    try:
        print(f"📄 Getting text for file_id: {file_id}, page: {page_num}")
        
        if file_id not in pdf_storage:
            raise HTTPException(status_code=404, detail="PDF not found")
        
        stored_data = pdf_storage[file_id]
        text_items = stored_data.get("text_items", [])
        text_metadata = stored_data.get("text_metadata", {})
        
        # Filter text items for the requested page
        page_text_items = [item for item in text_items if item.get("page") == page_num]
        
        # Filter metadata for the requested page
        page_metadata = {}
        for key, metadata in text_metadata.items():
            if metadata.get("page") == page_num:
                page_metadata[key] = metadata
        
        print(f"📊 Found {len(page_text_items)} text items for page {page_num}")
        
        return {
            "success": True,
            "page": page_num,
            "textItems": page_text_items,
            "textMetadata": page_metadata,
            "totalItems": len(page_text_items)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ GET PAGE TEXT ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get page text: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "version": "v3.0.0",
        "features": [
            "Multi-Page Support",
            "Intelligent Alignment",
            "Station Name Detection",
            "Enhanced Font Matching",
            "Visual Boldness Analysis",
            "Color Preservation"
        ]
    }

# Vercel serverless handler
def handler(request, context):
    """Vercel serverless function handler"""
    return app(request, context)

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Advanced PDF Editor Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
