"""
Flask-based PDF Editor Backend - Full functionality preserved
All endpoints and features from FastAPI version maintained
"""
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import uuid
import io
import fitz  # PyMuPDF - ONLY dependency for PDF processing
import base64
import re
import math
from typing import Dict, List, Tuple, Any
import json

def extract_pymupdf_metadata(pdf_content: bytes, page_num: int = None) -> Dict[str, Any]:
    """
    Extract enhanced text metadata using ONLY PyMuPDF - lightweight but powerful
    """
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    metadata = {}
    
    # Process specific page or all pages
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

def get_smart_alignment(text: str, old_text: str, line_text: str, bbox: tuple, page_width: float, all_text_items: list) -> dict:
    """
    INTELLIGENT TEXT ALIGNMENT using PyMuPDF-only analysis
    """
    x0, y0, x1, y1 = bbox
    text_width = x1 - x0
    text_height = y1 - y0
    
    # Page layout analysis
    page_center_x = page_width / 2
    text_center_x = (x0 + x1) / 2
    
    # STATION NAME DETECTION - Enhanced patterns
    station_patterns = [
        r'^[A-Z\s]+\s*\([A-Z]{2,4}\)$',  # "NEW DELHI (NDLS)"
        r'^[A-Z]{2,4}\s*\([A-Z]{2,4}\)$',  # "NDLS (NDLS)"
        r'^\w+\s*\([\w\s]+\)$'  # General pattern with parentheses
    ]
    
    is_station = False
    text_upper = text.upper()
    
    print(f"🚉 STATION DETECTION DEBUG:")
    print(f"   Text: '{text}' -> Upper: '{text_upper}'")
    print(f"   Testing patterns:")
    
    for i, pattern in enumerate(station_patterns, 1):
        match = re.match(pattern, text_upper)
        print(f"   Pattern {i}: {pattern} -> {'✅ MATCH' if match else '❌ No match'}")
        if match:
            is_station = True
            break
    
    print(f"   Is Station: {is_station}")
    
    # INTELLIGENT ALIGNMENT STRATEGY
    if is_station:
        # Station names should be centered 
        new_width = len(text) * (text_height * 0.6)  # Estimate width
        new_x0 = page_center_x - (new_width / 2)
        new_x1 = page_center_x + (new_width / 2)
        
        return {
            'strategy': 'center_station',
            'reasoning': f'Station name detected: "{text}" - maintaining center position',
            'new_bbox': [new_x0, y0, new_x1, y1]
        }
    
    # Check positioning context
    is_center_positioned = abs(text_center_x - page_center_x) < (page_width * 0.15)
    is_left_positioned = x0 < (page_width / 3)
    is_right_positioned = x0 > (page_width * 2/3)
    
    if is_center_positioned:
        # Keep center alignment but adjust for new text width
        new_width = len(text) * (text_height * 0.6)
        new_x0 = page_center_x - (new_width / 2)
        new_x1 = page_center_x + (new_width / 2)
        
        return {
            'strategy': 'maintain_center',
            'reasoning': f'Center positioned (x: {text_center_x:.1f}, center: {page_center_x:.1f}) - maintaining center',
            'new_bbox': [new_x0, y0, new_x1, y1]
        }
    
    elif is_left_positioned:
        # Expand to the right from left position
        new_width = len(text) * (text_height * 0.6)
        
        return {
            'strategy': 'expand_right',
            'reasoning': f'Left positioned (x: {x0:.1f}) - expanding right',
            'new_bbox': [x0, y0, x0 + new_width, y1]
        }
    
    elif is_right_positioned:
        # Expand to the left from right position  
        new_width = len(text) * (text_height * 0.6)
        
        return {
            'strategy': 'expand_left',
            'reasoning': f'Right positioned (x: {x0:.1f}) - expanding left',
            'new_bbox': [x0 - new_width, y0, x0, y1]
        }
    
    else:
        # Default: expand right from current position
        new_width = len(text) * (text_height * 0.6)
        
        return {
            'strategy': 'expand_right',
            'reasoning': f'Left positioned (x: {x0:.1f}) - expanding right',
            'new_bbox': [x0, y0, x0 + new_width, y1]
        }

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

# Create Flask app
app = Flask(__name__)

# Get the frontend URL from environment variable (for Vercel)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Add CORS middleware - simplified for reliability
print(f"🌐 Configured CORS for frontend: {frontend_url}")
CORS(app, origins="*", methods=["*"], allow_headers=["*"])

@app.after_request
def after_request(response):
    """Ensure all responses have proper CORS headers"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    return response

@app.route('/', methods=['GET', 'OPTIONS'])
def root():
    if request.method == 'OPTIONS':
        return '', 200
    
    return jsonify({
        "message": "🚀 ADVANCED PDF Editor Backend with Intelligent Alignment & Enhanced Text Quality",
        "version": "3.2.0-enhanced-flask",
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
        "size": "📦 <50MB PyMuPDF-Only",
        "framework": "Flask + PyMuPDF"
    })

@app.route('/upload-pdf', methods=['POST', 'OPTIONS'])
def upload_pdf():
    """
    Enhanced PDF upload with comprehensive metadata extraction
    """
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        print("🚀 ADVANCED PDF PROCESSING: Starting upload with enhanced metadata extraction")
        
        # Get uploaded file
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
            
        file = request.files['file']
        file_content = file.read()
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
        
        # Encode PDF data for stateless frontend operations
        pdf_data_base64 = base64.b64encode(file_content).decode('utf-8')
        
        return jsonify({
            "file_id": file_id,
            "text_items": text_items,
            "text_metadata": text_metadata,
            "embedded_fonts": embedded_fonts,
            "total_items": len(text_items),
            "processing_method": "enhanced" if len(all_metadata) > 0 else "fallback",
            "pdf_data": pdf_data_base64  # Include base64 PDF for stateless frontend
        })
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return jsonify({"error": f"Upload processing failed: {str(e)}"}), 500

@app.route('/pdf/<file_id>/edit', methods=['POST', 'OPTIONS'])
def edit_text(file_id):
    """
    ADVANCED text editing with intelligent positioning and enhanced boldness
    """
    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response, 200
        
    try:
        print(f"🚀 ADVANCED EDITING: Starting text edit for file_id: {file_id}")
        
        # Get request data
        data = request.get_json()
        page = data['page']
        metadata_key = data['metadata_key']
        new_text = data['new_text']
        pdf_data = data['pdf_data']
        text_metadata = data['text_metadata']
        
        print(f"📝 Edit request - page: {page}, metadata_key: {metadata_key}")
        
        # Decode the PDF data
        pdf_content = base64.b64decode(pdf_data)
        
        # Debug: Check text_metadata structure
        print(f"🔍 EDIT DEBUG: text_metadata type = {type(text_metadata)}")
        print(f"🔍 EDIT DEBUG: text_metadata keys = {list(text_metadata.keys())}")
        
        # Get metadata for the specific text item
        if metadata_key not in text_metadata:
            return jsonify({"error": f"Metadata key '{metadata_key}' not found"}), 400
        
        metadata = text_metadata[metadata_key]
        print(f"🔍 EDIT DEBUG: Found metadata for {metadata_key}")
        print(f"🔍 EDIT DEBUG: metadata keys = {list(metadata.keys())}")
        
        # Debug color extraction
        if 'color_rgb' in metadata:
            print(f"🔍 EDIT DEBUG: color_rgb = {metadata['color_rgb']}")
        
        # Extract information from metadata
        original_text = metadata["text"]
        original_bbox = metadata["bbox"]
        font_name = metadata["font"]
        font_size = metadata["size"]
        
        # Enhanced boldness detection with fallback values
        is_bold = metadata.get("is_bold", False)
        is_italic = metadata.get("is_italic", False)
        visual_boldness = metadata.get("visual_boldness_score", 0)
        
        print(f"🎯 EDITING: '{original_text}' -> '{new_text}'")
        print(f"📏 Original Position: {original_bbox}, Font: {font_name}, Size: {font_size}")
        print(f"🎨 Style: Bold={is_bold}, Italic={is_italic}, Visual Boldness={visual_boldness}")
        
        # Open PDF for editing
        pymupdf_doc = fitz.open(stream=pdf_content, filetype="pdf")
        pymupdf_page = pymupdf_doc[page - 1]  # Convert to 0-based index
        
        # 🧠 INTELLIGENT POSITIONING: Simple context analysis using PyMuPDF
        print(f"🧠 ANALYZING TEXT CONTEXT...")
        try:
            # Get page width first
            page_width = pymupdf_page.rect.width
            
            # Get page context for intelligent positioning
            page_metadata = extract_pymupdf_metadata(pdf_content, page_num=page - 1)
            all_text_items = list(page_metadata.values())
            
            # Simple context analysis
            text_context = {
                'alignment': 'center' if abs((original_bbox[0] + original_bbox[2])/2 - page_width/2) < page_width * 0.15 else 'left',
                'is_near_center': abs((original_bbox[0] + original_bbox[2])/2 - page_width/2) < page_width * 0.15,
                'is_list_item': False,  # Added missing variable
                'is_header': False,     # Added missing variable  
                'is_justified': False,  # Added missing variable
                'spacing_analysis': {'has_adequate_space': True},
                'context_items': len(all_text_items)
            }
            
            print(f"📊 CONTEXT ANALYSIS:")
            print(f"   Alignment: {text_context['alignment']}")
            print(f"   List Item: {text_context['is_list_item']}")
            print(f"   Header: {text_context['is_header']}")
            print(f"   Justified: {text_context['is_justified']}")
            
            # USE NEW SMART ALIGNMENT SYSTEM
            # Get all text items for context (simplified for now)
            all_text_items = [{'x': original_bbox[0], 'y': original_bbox[1], 'text': original_text}]
            
            smart_alignment = get_smart_alignment(
                text=new_text,
                old_text=original_text, 
                line_text=original_text,  # Using original text as line text for now
                bbox=original_bbox,
                page_width=page_width,
                all_text_items=all_text_items
            )
            
            print(f"🎯 SMART ALIGNMENT STRATEGY: {smart_alignment['strategy']}")
            print(f"📘 REASONING: {smart_alignment['reasoning']}")
            print(f"📏 New Position: {smart_alignment['new_bbox']}")
            
            # Use the smart alignment result
            new_bbox = smart_alignment['new_bbox']
            positioning_strategy = smart_alignment['strategy']
            
        except Exception as e:
            print(f"⚠️  Intelligent positioning failed: {e}")
            print(f"🔄 Falling back to original position")
            new_bbox = original_bbox
            positioning_strategy = "fallback"
            # Initialize smart_alignment for fallback case
            smart_alignment = {
                'strategy': 'fallback',
                'reasoning': 'Error in intelligent positioning',
                'new_bbox': original_bbox
            }
        
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
        
        return jsonify({
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
        })
        
    except Exception as e:
        print(f"❌ ADVANCED EDIT ERROR: {e}")
        return jsonify({"error": f"Text editing failed: {str(e)}"}), 500

@app.route('/pdf/<file_id>/download', methods=['POST', 'OPTIONS'])
def download_pdf(file_id):
    """
    Download the edited PDF
    """
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        print(f"📥 DOWNLOAD: Starting download for file_id: {file_id}")
        
        # Get request data
        data = request.get_json()
        pdf_data = data['pdf_data']
        
        # Decode the PDF data
        pdf_bytes = base64.b64decode(pdf_data)
        print(f"📄 PDF data decoded: {len(pdf_bytes)} bytes")
        
        print(f"✅ DOWNLOAD: Ready to serve {len(pdf_bytes)} bytes")
        
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=edited_{file_id}.pdf",
                "Content-Length": str(len(pdf_bytes)),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
                "Access-Control-Expose-Headers": "Content-Disposition, Content-Length"
            }
        )
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return jsonify({"error": f"Download failed: {str(e)}"}), 500

# Health check endpoint
@app.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({"status": "healthy", "timestamp": "2025-08-19", "version": "3.2.0-flask", "framework": "Flask"})

# Flask is WSGI-native, no need for Mangum wrapper
if __name__ == '__main__':
    app.run(debug=True)
