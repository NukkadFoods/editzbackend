from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import os
import uuid
import io
import fitz  # PyMuPDF
import base64
import re
import math
from typing import Dict, List, Tuple, Any

app = FastAPI(title="PDF Editor Backend - Advanced")

# Enhanced CORS configuration for dynamic Vercel URLs
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

@app.get("/")
async def root():
    return {
        "message": "🚀 MINIMAL PDF Editor Backend - PyMuPDF + FastAPI",
        "version": "4.0.0-minimal",
        "features": [
            "Enhanced Boldness Detection", 
            "Perfect Font Size Matching",
            "Intelligent Text Positioning",
            "Universal CORS Support",
            "Lightweight Deployment"
        ],
        "size": "< 50MB - Vercel Ready"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment verification"""
    return {
        "status": "healthy",
        "service": "pdf-editor-backend-minimal",
        "dependencies": ["PyMuPDF", "FastAPI"],
        "vercel_ready": True
    }

class EditRequest(BaseModel):
    page: int
    metadata_key: str
    new_text: str

class FrontendEditRequest(BaseModel):
    pageNumber: int
    oldText: str
    newText: str
    textIndex: int = None

def extract_enhanced_metadata(pdf_content: bytes) -> Dict[str, Any]:
    """Extract text metadata with enhanced boldness and size detection using only PyMuPDF"""
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    metadata = {}
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Get text with detailed font information
        text_dict = page.get_text("dict")
        
        for block in text_dict["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text:  # Only process non-empty text
                            
                            # Enhanced font analysis
                            font_name = span["font"]
                            font_size = span["size"]
                            flags = span["flags"]
                            bbox = span["bbox"]
                            color = span["color"]
                            
                            # ENHANCED BOLDNESS DETECTION
                            # Method 1: Font name analysis
                            font_bold_indicators = ['bold', 'Bold', 'BOLD', 'heavy', 'Heavy', 'black', 'Black']
                            is_bold_by_name = any(indicator in font_name for indicator in font_bold_indicators)
                            
                            # Method 2: Font flags analysis (bit 16 = bold)
                            is_bold_by_flags = bool(flags & 2**4)  # Bold flag
                            
                            # Method 3: Font weight analysis from PyMuPDF
                            font_weight = 400  # Default
                            if is_bold_by_name or is_bold_by_flags:
                                font_weight = 700
                            
                            # Calculate boldness confidence
                            boldness_score = 0
                            if is_bold_by_name:
                                boldness_score += 0.6
                            if is_bold_by_flags:
                                boldness_score += 0.4
                            
                            # SIZE ANALYSIS
                            # Get actual rendered size vs font size
                            actual_height = bbox[3] - bbox[1]
                            size_ratio = actual_height / font_size if font_size > 0 else 1.0
                            
                            # RGB Color conversion
                            if isinstance(color, int):
                                # Convert from integer to RGB
                                r = (color >> 16) & 255
                                g = (color >> 8) & 255  
                                b = color & 255
                                rgb_color = (r/255.0, g/255.0, b/255.0)
                            else:
                                rgb_color = (0, 0, 0)  # Default black
                            
                            # Create unique key
                            key = f"page_{page_num+1}_text_{len(metadata)}"
                            
                            metadata[key] = {
                                "text": text,
                                "bbox": list(bbox),
                                "page": page_num + 1,
                                "font_name": font_name,
                                "font_size": font_size,
                                "actual_height": actual_height,
                                "size_ratio": size_ratio,
                                "color": rgb_color,
                                "color_int": color,
                                "flags": flags,
                                "is_bold": is_bold_by_name or is_bold_by_flags,
                                "boldness_score": boldness_score,
                                "font_weight": font_weight,
                                "is_italic": bool(flags & 2**1),  # Italic flag
                            }
    
    doc.close()
    return metadata

def get_optimal_font_mapping(original_font: str, is_bold: bool, boldness_score: float) -> str:
    """Get the best PyMuPDF font mapping for text replacement"""
    
    # Enhanced font mapping with boldness consideration
    if boldness_score > 0.5 or is_bold:
        # Bold text mappings
        bold_mappings = {
            'Arial': 'helv-bold',
            'ArialMT': 'helv-bold', 
            'Arial-Bold': 'helv-bold',
            'Arial-BoldMT': 'helv-bold',
            'Helvetica': 'helv-bold',
            'Helvetica-Bold': 'helv-bold',
            'Times': 'times-bold',
            'Times-Roman': 'times-bold',
            'Times-Bold': 'times-bold',
            'TimesNewRoman': 'times-bold',
            'TimesNewRoman-Bold': 'times-bold',
            'Courier': 'cour-bold',
            'CourierNew': 'cour-bold',
            'Courier-Bold': 'cour-bold',
        }
        
        # Check for exact match first
        for pattern, font in bold_mappings.items():
            if pattern.lower() in original_font.lower():
                return font
        
        # Default bold
        return 'helv-bold'
    
    else:
        # Regular text mappings
        regular_mappings = {
            'Arial': 'helv',
            'ArialMT': 'helv',
            'Helvetica': 'helv', 
            'Times': 'times-roman',
            'Times-Roman': 'times-roman',
            'TimesNewRoman': 'times-roman',
            'Courier': 'cour',
            'CourierNew': 'cour',
        }
        
        # Check for exact match first
        for pattern, font in regular_mappings.items():
            if pattern.lower() in original_font.lower():
                return font
        
        # Default regular
        return 'helv'

def get_smart_positioning(text: str, old_text: str, bbox: tuple, page_width: float) -> tuple:
    """Determine optimal positioning for new text"""
    x0, y0, x1, y1 = bbox
    text_width = x1 - x0
    text_center_x = (x0 + x1) / 2
    page_center_x = page_width / 2
    
    # Calculate new width based on text length ratio
    if old_text and len(old_text) > 0:
        length_ratio = len(text) / len(old_text)
        new_width = text_width * length_ratio
    else:
        new_width = text_width
    
    # Check if text appears to be centered
    center_tolerance = page_width * 0.15
    is_centered = abs(text_center_x - page_center_x) < center_tolerance
    
    if is_centered:
        # Maintain center position
        new_x0 = text_center_x - (new_width / 2)
        new_x1 = text_center_x + (new_width / 2)
        return (new_x0, y0, new_x1, y1)
    
    elif x0 > page_width * 0.7:
        # Right-aligned text - maintain right edge
        new_x0 = x1 - new_width
        return (new_x0, y0, x1, y1)
    
    else:
        # Left-aligned text - expand to the right
        new_x1 = x0 + new_width
        return (x0, y0, new_x1, y1)

@app.post("/upload")
async def upload_pdf_legacy(file: UploadFile = File(...)):
    """Legacy upload endpoint for backward compatibility"""
    return await upload_pdf_main(file)

@app.post("/upload-pdf")
async def upload_pdf_main(file: UploadFile = File(...)):
    """Upload PDF and extract metadata for editing"""
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        # Read file content
        content = await file.read()
        print(f"📄 Processing PDF: {file.filename} ({len(content)} bytes)")
        
        # Extract metadata using only PyMuPDF
        metadata = extract_enhanced_metadata(content)
        
        print(f"✅ Extracted metadata for {len(metadata)} text items")
        
        # Store the original PDF temporarily
        file_id = str(uuid.uuid4())
        temp_file_path = f"/tmp/{file_id}.pdf"
        
        with open(temp_file_path, "wb") as f:
            f.write(content)
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "metadata": metadata,
            "total_items": len(metadata),
            "pages_processed": len(set(item.get('page', 1) for item in metadata.values()))
        }
        
    except Exception as e:
        print(f"❌ Error processing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.post("/edit")
async def edit_pdf_legacy(edit_request: EditRequest):
    """Legacy edit endpoint for backward compatibility"""
    return await edit_pdf_main(edit_request)

@app.post("/pdf/{file_id}/edit")
async def edit_pdf_frontend(file_id: str, edit_request: FrontendEditRequest):
    """Frontend-compatible edit endpoint"""
    
    # Get stored metadata for this file
    temp_file_path = f"/tmp/{file_id}.pdf"
    if not os.path.exists(temp_file_path):
        # For now, use temp_file as fallback
        temp_file_path = "/tmp/temp_file.pdf"
        if not os.path.exists(temp_file_path):
            raise HTTPException(status_code=404, detail="PDF file not found")
    
    # Read and extract metadata to find matching text
    with open(temp_file_path, "rb") as f:
        pdf_content = f.read()
    
    metadata = extract_enhanced_metadata(pdf_content)
    
    # Find text item that matches oldText on the specified page
    matching_key = None
    for key, item in metadata.items():
        if (item['page'] == edit_request.pageNumber and 
            edit_request.oldText.strip() in item['text'].strip()):
            matching_key = key
            break
    
    if not matching_key:
        # If exact match not found, try partial match
        for key, item in metadata.items():
            if (item['page'] == edit_request.pageNumber and 
                item['text'].strip() in edit_request.oldText.strip()):
                matching_key = key
                break
    
    if not matching_key:
        return {
            "success": False,
            "message": f"Text '{edit_request.oldText}' not found on page {edit_request.pageNumber}",
            "available_texts": [item['text'] for item in metadata.values() if item['page'] == edit_request.pageNumber]
        }
    
    # Convert to internal EditRequest format
    internal_request = EditRequest(
        page=edit_request.pageNumber,
        metadata_key=matching_key,
        new_text=edit_request.newText
    )
    
    result = await edit_pdf_main(internal_request)
    
    # Convert result to frontend format
    if result.get("success"):
        return {
            "success": True,
            "message": "Text edited successfully",
            "fileId": file_id
        }
    else:
        return {
            "success": False,
            "message": result.get("detail", "Edit failed")
        }

async def edit_pdf_main(edit_request: EditRequest):
    """Enhanced PDF text editing with perfect boldness and size matching"""
    
    try:
        file_id = "temp_file"  # In production, get from request
        temp_file_path = f"/tmp/{file_id}.pdf"
        
        if not os.path.exists(temp_file_path):
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        print(f"🔄 Starting ENHANCED text replacement on page {edit_request.page}")
        print(f"📝 Key: {edit_request.metadata_key}")
        print(f"📝 New text: '{edit_request.new_text}'")
        
        # Read the original PDF
        with open(temp_file_path, "rb") as f:
            pdf_content = f.read()
        
        # Extract metadata
        metadata = extract_enhanced_metadata(pdf_content)
        
        if edit_request.metadata_key not in metadata:
            raise HTTPException(status_code=404, detail="Text not found in PDF")
        
        target_item = metadata[edit_request.metadata_key]
        target_page = edit_request.page - 1  # Convert to 0-based indexing
        
        print(f"🎯 Target: '{target_item['text']}' on page {edit_request.page}")
        print(f"📊 Original bbox: {target_item['bbox']}")
        print(f"🎨 Font: {target_item['font_name']} (size: {target_item['font_size']})")
        print(f"💪 Boldness: {target_item['boldness_score']:.2f} (is_bold: {target_item['is_bold']})")
        print(f"📐 Size ratio: {target_item['size_ratio']:.2f}")
        
        # Open PDF for editing
        pdf_doc = fitz.open(stream=pdf_content, filetype="pdf")
        page = pdf_doc[target_page]
        
        # Get optimal font mapping
        optimal_font = get_optimal_font_mapping(
            target_item['font_name'],
            target_item['is_bold'], 
            target_item['boldness_score']
        )
        
        # Calculate optimal size - use actual rendered height for accuracy
        optimal_size = target_item['actual_height'] * 0.8  # Adjust for better fit
        
        # Get smart positioning
        new_bbox = get_smart_positioning(
            edit_request.new_text,
            target_item['text'],
            target_item['bbox'],
            page.rect.width
        )
        
        print(f"🔤 Font mapping: {target_item['font_name']} → {optimal_font}")
        print(f"📏 Size: {target_item['font_size']:.1f} → {optimal_size:.1f} (height: {target_item['actual_height']:.1f})")
        print(f"📍 Position: {target_item['bbox']} → {new_bbox}")
        
        # Remove original text
        original_rect = fitz.Rect(target_item['bbox'])
        page.add_redact_annot(original_rect)
        page.apply_redactions()
        
        # Insert new text with enhanced parameters
        new_rect = fitz.Rect(new_bbox)
        
        result = page.insert_text(
            new_rect.tl,  # Top-left point
            edit_request.new_text,
            fontsize=optimal_size,
            fontname=optimal_font,
            color=target_item['color'],  # Use exact RGB color
            overlay=True
        )
        
        if result > 0:
            print(f"✅ Text successfully replaced with ENHANCED BOLDNESS & SIZE MATCHING")
            print(f"🎨 Color preserved: RGB{target_item['color']}")
        else:
            print(f"⚠️ Text insertion may have issues")
        
        # Generate edited PDF
        output_buffer = io.BytesIO()
        pdf_doc.save(output_buffer)
        pdf_doc.close()
        
        edited_content = output_buffer.getvalue()
        output_buffer.close()
        
        # Return base64 encoded PDF
        encoded_pdf = base64.b64encode(edited_content).decode('utf-8')
        
        return {
            "success": True,
            "edited_pdf": encoded_pdf,
            "changes": {
                "page": edit_request.page,
                "original_text": target_item['text'],
                "new_text": edit_request.new_text,
                "font_used": optimal_font,
                "original_font": target_item['font_name'],
                "original_size": target_item['font_size'],
                "optimal_size": optimal_size,
                "size_ratio": target_item['size_ratio'],
                "boldness_score": target_item['boldness_score'],
                "is_bold": target_item['is_bold'],
                "original_bbox": target_item['bbox'],
                "new_bbox": list(new_bbox),
                "color_preserved": target_item['color']
            }
        }
        
    except Exception as e:
        print(f"❌ Error in text replacement: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error editing PDF: {str(e)}")

@app.get("/pdf/{file_id}/download")
async def download_pdf(file_id: str):
    """Download the edited PDF file"""
    
    # For now, return the temp file (in production, you'd manage file storage properly)
    temp_file_path = f"/tmp/{file_id}.pdf"
    if not os.path.exists(temp_file_path):
        temp_file_path = "/tmp/temp_file.pdf"
        if not os.path.exists(temp_file_path):
            raise HTTPException(status_code=404, detail="PDF file not found")
    
    try:
        with open(temp_file_path, "rb") as f:
            pdf_content = f.read()
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=edited_{file_id}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading PDF: {str(e)}")

# For Vercel serverless deployment
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
