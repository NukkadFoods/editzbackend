from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import os
import uuid
import io
import fitz  # PyMuPDF
import pdfplumber  # Better font extraction
import pikepdf  # Direct PDF content editing
from fontTools.ttLib import TTFont  # Font analysis
import cv2  # Visual validation
import numpy as np
import base64
from typing import Optional, Dict, Any
import tempfile

app = FastAPI(title="PDF Editor Backend")

# Get the frontend URL from environment variable (for Vercel)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "https://editz.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
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
    return {"message": "PDF Editor Backend is running!"}

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """ADVANCED PDF processing with embedded font extraction and precise coordinates"""
    try:
        print("🚀 ADVANCED PDF PROCESSING: Starting upload with embedded font extraction")
        
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
        
        # STEP 2: Use PyMuPDF for PRECISE text extraction with coordinates
        pdf_document = fitz.open(stream=file_content, filetype="pdf")
        text_items = []
        text_metadata = {}
        item_counter = 0
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Get text with EXACT formatting and positioning
            text_dict = page.get_text("dict", flags=11)  # Flags for maximum detail
            
            for block in text_dict["blocks"]:
                if "lines" in block:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if span["text"].strip():  # Only non-empty text
                                item_counter += 1
                                metadata_key = f"text_item_{item_counter}"
                                
                                # Extract PRECISE font and formatting information
                                font_info = span["font"]
                                font_size = span["size"]
                                font_flags = span["flags"]
                                text_color = span["color"]
                                bbox = span["bbox"]
                                
                                # Analyze font properties for EXACT boldness detection
                                is_bold = bool(font_flags & 2**4)  # Bold flag
                                is_italic = bool(font_flags & 2**6)  # Italic flag
                                
                                # Check if font is embedded
                                embedded_font_info = embedded_fonts.get(f"/{font_info}", {})
                                has_embedded_font = embedded_font_info.get('is_embedded', False)
                                
                                # Enhanced boldness detection from font name
                                font_name_lower = font_info.lower()
                                name_indicates_bold = any(keyword in font_name_lower for keyword in ['bold', 'black', 'heavy', 'demi', 'semibold'])
                                
                                # Final boldness determination
                                final_is_bold = is_bold or name_indicates_bold
                                
                                # Create text item with ENHANCED metadata
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
                                    "is_bold": final_is_bold,
                                    "is_italic": is_italic,
                                    "has_embedded_font": has_embedded_font
                                }
                                
                                # Create COMPREHENSIVE metadata for perfect editing
                                text_metadata[metadata_key] = {
                                    "text": span["text"],
                                    "bbox": list(bbox),
                                    "font": font_info,
                                    "size": font_size,
                                    "color": text_color,
                                    "flags": font_flags,
                                    "page": page_num + 1,
                                    "is_bold": final_is_bold,
                                    "is_italic": is_italic,
                                    "has_embedded_font": has_embedded_font,
                                    "embedded_font_data": embedded_font_info.get('font_data'),
                                    "pymupdf_font": font_info,  # Original PyMuPDF font reference
                                    "matrix": span.get("transform", [1, 0, 0, 1, 0, 0]),  # Transformation matrix
                                    "char_spacing": span.get("char_spacing", 0),
                                    "line_height": bbox[3] - bbox[1]
                                }
                                
                                text_items.append(text_item)
                                
                                print(f"🔍 ENHANCED EXTRACTION: '{span['text'][:20]}...' -> Font: {font_info}, Size: {font_size}, Bold: {final_is_bold}, Embedded: {has_embedded_font}")
        
        pdf_document.close()
        
        # Encode original PDF as base64 for frontend storage
        pdf_data_base64 = base64.b64encode(file_content).decode('utf-8')
        
        response = {
            "success": True,
            "fileId": file_id,
            "filename": file.filename,
            "textItems": text_items,
            "pdfData": pdf_data_base64,
            "textMetadata": text_metadata,
            "backendVersion": "ADVANCED_EMBEDDED_FONTS_V3",
            "extractedItems": len(text_items),
            "embeddedFonts": len(embedded_fonts)
        }
        
        print(f"✅ ADVANCED PDF processing complete: {len(text_items)} text items, {len(embedded_fonts)} embedded fonts")
        return response
        
    except Exception as e:
        print(f"❌ ADVANCED PDF ERROR: {e}")
        return {"success": False, "error": str(e), "filename": file.filename if file else "unknown"}

@app.post("/pdf/{file_id}/edit")
async def edit_text(file_id: str, edit_request: EditRequest):
    """Edit text in PDF using provided PDF data"""
    try:
        print(f"DEBUG: Starting text edit for file_id: {file_id}")
        print(f"DEBUG: Edit request - page: {edit_request.page}, metadata_key: {edit_request.metadata_key}")
        
        # Decode PDF data from request
        try:
            pdf_content = base64.b64decode(edit_request.pdf_data)
        except Exception as e:
            print(f"ERROR: Failed to decode PDF data: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid PDF data")
        
        # Open PDF document
        pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
        
        # Get the specific text metadata
        if edit_request.metadata_key not in edit_request.text_metadata:
            print(f"ERROR: Metadata key not found: {edit_request.metadata_key}")
            raise HTTPException(status_code=400, detail="Text metadata not found")
        
        metadata = edit_request.text_metadata[edit_request.metadata_key]
        
        # Get the page
        page = pdf_document[edit_request.page - 1]
        
        # Remove the original text first
        original_bbox = fitz.Rect(metadata["bbox"])
        
        # Create a white rectangle to cover the original text with padding
        clear_padding = 2
        clear_rect = fitz.Rect(
            original_bbox.x0 - clear_padding,
            original_bbox.y0 - clear_padding, 
            original_bbox.x1 + clear_padding,
            original_bbox.y1 + clear_padding
        )
        page.draw_rect(clear_rect, color=(1, 1, 1), fill=(1, 1, 1))
        
        # Prepare font and text properties
        font_name = metadata["font"]
        font_size = metadata["size"]
        text_color = metadata.get("color", 0)  # Default to black
        
        # Convert color from integer to tuple if needed
        if isinstance(text_color, int):
            # Convert from integer color to RGB tuple
            r = (text_color >> 16) & 255
            g = (text_color >> 8) & 255
            b = text_color & 255
            text_color = (r/255, g/255, b/255)
        
        # Get exact font properties and coordinates (already in PyMuPDF format)
        font_name = metadata["exact_fontname"]
        font_size = metadata["size"]
        is_bold = metadata.get("is_bold", False)
        is_italic = metadata.get("is_italic", False)
        text_color = metadata.get("color", 0)
        
        # Convert color from integer to tuple if needed
        if isinstance(text_color, int):
            # Convert from integer color to RGB tuple
            r = (text_color >> 16) & 255
            g = (text_color >> 8) & 255
            b = text_color & 255
            text_color = (r/255, g/255, b/255)
        
        print(f"DEBUG: EXACT FONT INFO - Font: {font_name}, Size: {font_size}, Bold: {is_bold}, Italic: {is_italic}")
        
        # Map exact font names to PyMuPDF fonts with PRECISE bold matching
        fontname = "helv"  # Default
        
        # Use the exact font name to determine the best PyMuPDF font
        font_lower = font_name.lower()
        
        # More precise font mapping based on actual font names
        if any(name in font_lower for name in ['arial', 'helvetica']):
            if is_bold and is_italic:
                fontname = "hebo"  # Use bold as primary
            elif is_bold:
                fontname = "hebo"  # Helvetica Bold
            elif is_italic:
                fontname = "heit"  # Helvetica Italic
            else:
                fontname = "helv"  # Regular Helvetica
        elif any(name in font_lower for name in ['times', 'roman']):
            if is_bold and is_italic:
                fontname = "tibo"  # Use bold as primary
            elif is_bold:
                fontname = "tibo"  # Times Bold
            elif is_italic:
                fontname = "tiit"  # Times Italic
            else:
                fontname = "times"  # Regular Times
        elif any(name in font_lower for name in ['courier', 'mono']):
            if is_bold:
                fontname = "cobo"  # Courier Bold
            else:
                fontname = "cour"  # Regular Courier
        elif any(name in font_lower for name in ['calibri', 'segoe']):
            if is_bold:
                fontname = "hebo"  # Map to Helvetica Bold
            else:
                fontname = "helv"  # Map to Helvetica
        else:
            # For unknown fonts, use bold detection from font name
            if is_bold or any(keyword in font_lower for keyword in ['bold', 'black', 'heavy', 'demi']):
                fontname = "hebo"  # Default to Helvetica Bold
            elif is_italic:
                fontname = "heit"  # Default to Helvetica Italic
            else:
                fontname = "helv"  # Default to Helvetica
        
        # Use EXACT font size from PyMuPDF
        precise_font_size = font_size
        
        print(f"DEBUG: MAPPED FONT - Original: {font_name} -> PyMuPDF: {fontname}, Size: {precise_font_size}")
        
        # For bold text that doesn't have a bold font variant, simulate boldness
        simulate_bold = is_bold and fontname in ["helv", "times", "cour"]
        
        new_text = edit_request.new_text
        
        if new_text.strip():
            # Calculate precise positioning - CENTER the new text in the original bounding box
            original_x = original_bbox.x0
            original_y = original_bbox.y0
            original_width = original_bbox.width
            original_height = original_bbox.height
            
            # Estimate the width of the new text using precise font size
            estimated_char_width = precise_font_size * 0.6  # Approximate character width
            estimated_new_text_width = len(edit_request.new_text) * estimated_char_width
            
            # CENTER the new text horizontally within the original bounding box
            if estimated_new_text_width <= original_width:
                # New text fits within original bounds - center it
                precise_x = original_x + (original_width - estimated_new_text_width) / 2
            else:
                # New text is longer - still center it around the original center point
                original_center_x = original_x + (original_width / 2)
                precise_x = original_center_x - (estimated_new_text_width / 2)
            
            # Use precise Y positioning with proper baseline
            precise_y = original_y + (original_height * 0.8)  # Adjust baseline to 80% of height
            
            # Insert new text with EXACT font properties
            if simulate_bold:
                # For bold text without bold font, render text multiple times with slight offset
                for offset in [(0, 0), (0.3, 0), (0, 0.3), (0.3, 0.3)]:
                    page.insert_text(
                        (precise_x + offset[0], precise_y + offset[1]),
                        new_text,
                        fontname=fontname,
                        fontsize=precise_font_size,
                        color=text_color
                    )
                print(f"DEBUG: SIMULATED BOLD - Text rendered with multiple offsets")
            else:
                # Regular text insertion
                page.insert_text(
                    (precise_x, precise_y),
                    new_text,
                    fontname=fontname,
                    fontsize=precise_font_size,
                    color=text_color
                )
            
            print(f"DEBUG: EXACT FONT RENDERING - Font: {fontname}, Size: {precise_font_size}, Bold: {is_bold}, Simulate: {simulate_bold}")
        
        # Get the modified PDF as bytes
        modified_pdf_bytes = pdf_document.write()
        pdf_document.close()
        
        # Encode modified PDF as base64
        modified_pdf_base64 = base64.b64encode(modified_pdf_bytes).decode('utf-8')
        
        print(f"DEBUG: Text edit successful")
        
        return {
            "success": True,
            "message": "Text edited successfully",
            "pdfData": modified_pdf_base64
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in edit_text: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pdf/{file_id}/download")
async def download_pdf(file_id: str, download_request: DownloadRequest):
    """Download the modified PDF using provided PDF data"""
    try:
        print(f"DEBUG: Starting download for file_id: {file_id}")
        
        # Decode PDF data from request
        try:
            pdf_content = base64.b64decode(download_request.pdf_data)
        except Exception as e:
            print(f"ERROR: Failed to decode PDF data: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid PDF data")
        
        print(f"DEBUG: Download successful, PDF size: {len(pdf_content)} bytes")
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=edited_{file_id}.pdf"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in download_pdf: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.get("/test-response")
async def test_response():
    """Test endpoint to verify response structure"""
    return {
        "success": True,
        "fileId": "test-123",
        "filename": "test.pdf",
        "textItems": [{"text": "test", "page": 1}],
        "pdfData": "dGVzdA==",  # base64 encoded "test"
        "textMetadata": {"test_key": "test_value"}
    }
