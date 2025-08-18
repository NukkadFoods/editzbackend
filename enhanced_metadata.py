# Enhanced PDF Text Metadata Extractor
# Based on the comprehensive metaplan.txt

import fitz  # PyMuPDF
import re
import math
import cv2
import numpy as np

def extract_complete_text_metadata(pdf_content, target_text=None, page_num=0):
    """
    Extracts ALL text properties needed for perfect matching
    """
    
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        page = doc.load_page(page_num)
        
        # Use dict method instead of rawdict for better compatibility
        blocks = page.get_text("dict")["blocks"]
        
        results = []

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue

                    if target_text and target_text not in text:
                        continue

                    try:
                        # === BASIC PROPERTIES ===
                        raw_font_name = span.get("font", "")
                        font_size = round(span.get("size", 0), 2)
                        color_int = span.get("color", 0)
                        
                        # Convert color to RGB
                        r = (color_int >> 16) & 0xFF
                        g = (color_int >> 8) & 0xFF
                        b = color_int & 0xFF

                        # Bounding box and position
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        origin = span.get("origin", bbox[:2])  # fallback to bbox if no origin

                        # === FONT FLAGS ANALYSIS ===
                        flags = span.get("flags", 0)
                        is_superscript = bool(flags & 1)      # bit 0
                        is_italic = bool(flags & 2)           # bit 1
                        is_serif = bool(flags & 4)            # bit 2
                        is_monospace = bool(flags & 8)        # bit 3
                        is_bold = bool(flags & 16)            # bit 4
                        is_vertical = bool(flags & 32)        # bit 5
                        is_underline = bool(flags & 64)       # bit 6
                        is_strikeout = bool(flags & 128)      # bit 7

                        # === FONT NAME ANALYSIS ===
                        # Remove obfuscation prefix (e.g., ABCDEE+Helvetica-Bold)
                        clean_font_name = re.sub(r'^[A-Z0-9]{6}\+', '', raw_font_name)
                        font_name_lower = clean_font_name.lower()

                        # Weight detection
                        bold_keywords = ['bold', 'black', 'heavy', 'demi', 'semibold', 'extrabold', 'ultrabold']
                        light_keywords = ['thin', 'light', 'extralight', 'ultralight']
                        medium_keywords = ['medium', 'regular', 'normal']
                        
                        is_bold_name = any(kw in font_name_lower for kw in bold_keywords)
                        is_light_name = any(kw in font_name_lower for kw in light_keywords)
                        is_medium_name = any(kw in font_name_lower for kw in medium_keywords)
                        
                        # Italic detection
                        is_italic_name = 'italic' in font_name_lower or 'oblique' in font_name_lower

                        # Final determination
                        final_is_bold = is_bold or is_bold_name
                        final_is_italic = is_italic or is_italic_name

                        # === CHARACTER & WORD SPACING ===
                        char_spacing = span.get("charspace", 0)    # Tc operator
                        word_spacing = span.get("wordspace", 0)    # Tw operator

                        # === TEXT RENDERING MODE ===
                        render_mode = span.get("rendermode", 0)

                        # === TRANSFORM MATRIX ===
                        matrix = span.get("transform", [1, 0, 0, 1, 0, 0])  # [a, b, c, d, e, f]

                        # Calculate rotation angle (in degrees)
                        m_a, m_b, m_c, m_d = matrix[0], matrix[1], matrix[2], matrix[3]
                        rotation_rad = math.atan2(m_b, m_a)
                        rotation_deg = math.degrees(rotation_rad)

                        # Scale factors
                        scale_x = math.sqrt(m_a*m_a + m_b*m_b)
                        scale_y = math.sqrt(m_c*m_c + m_d*m_d)

                        # === VISUAL PROPERTIES ===
                        visual_boldness = estimate_visual_boldness_from_content(pdf_content, page_num, bbox)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]

                        # Character count and average width
                        char_count = len(text)
                        avg_char_width = text_width / char_count if char_count > 0 else 0

                        # === BUILD RESULT ===
                        result = {
                            # Text content
                            "text": text,
                            
                            # Font properties
                            "raw_font_name": raw_font_name,
                            "clean_font_name": clean_font_name,
                            "font_size": font_size,
                            "font_flags": flags,
                            "is_bold_flag": is_bold,
                            "is_italic_flag": is_italic,
                            "is_bold_name": is_bold_name,
                            "is_italic_name": is_italic_name,
                            "is_bold_final": final_is_bold,
                            "is_italic_final": final_is_italic,
                            "is_light": is_light_name,
                            "is_medium": is_medium_name,
                            "is_serif": is_serif,
                            "is_monospace": is_monospace,
                            "is_vertical": is_vertical,
                            
                            # Color
                            "color_rgb": (r, g, b),
                            "color_int": color_int,
                            
                            # Positioning
                            "bbox": bbox,
                            "origin": origin,
                            "page": page_num + 1,  # Convert 0-based to 1-based page numbering
                            "text_width": round(text_width, 2),
                            "text_height": round(text_height, 2),
                            
                            # Spacing
                            "char_spacing": round(char_spacing, 2),
                            "word_spacing": round(word_spacing, 2),
                            "avg_char_width": round(avg_char_width, 2),
                            
                            # Rendering
                            "render_mode": render_mode,
                            "underline": is_underline,
                            "strikeout": is_strikeout,
                            "superscript": is_superscript,
                            
                            # Transform
                            "transform_matrix": matrix,
                            "rotation_degrees": round(rotation_deg, 2),
                            "scale_x": round(scale_x, 4),
                            "scale_y": round(scale_y, 4),
                            
                            # Visual analysis
                            "visual_boldness_score": visual_boldness,
                            "char_count": char_count,
                        }
                        
                        results.append(result)

                    except Exception as e:
                        print(f"❌ Error processing span: {e} - Text: {text[:30]}")
                        continue

        doc.close()
        return results
    
    except Exception as e:
        print(f"❌ Error in extract_complete_text_metadata: {e}")
        return []


def estimate_visual_boldness_from_content(pdf_content, page_num, bbox, zoom=4):
    """
    Returns a visual boldness score based on stroke thickness.
    Higher score = bolder text.
    """
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        page = doc.load_page(page_num)
        
        # Ensure bbox has valid dimensions
        if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            return 0.0
        
        # High-res render for accuracy
        mat = fitz.Matrix(zoom, zoom)
        # Create a proper rect and scale bbox for high-res
        rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
        scaled_rect = rect * mat
        
        # Ensure the rect is valid and not empty
        if scaled_rect.is_empty or scaled_rect.width < 1 or scaled_rect.height < 1:
            return 0.0
            
        pix = page.get_pixmap(matrix=mat, clip=scaled_rect)
        
        # Check if pixmap is valid
        if not pix or pix.width == 0 or pix.height == 0:
            return 0.0
        
        # Convert to numpy array
        img_data = pix.samples
        if len(img_data) == 0:
            return 0.0
            
        img = np.frombuffer(img_data, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        # Handle different pixel formats
        if pix.n == 4:  # RGBA
            img = img[:, :, :3]  # Drop alpha channel
        elif pix.n == 1:  # Grayscale
            gray = img[:, :, 0]
        else:  # RGB
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Check if we have valid image data
        if gray.size == 0:
            return 0.0
        
        # Binary threshold (text is dark, background is light)
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        
        # Calculate text density as boldness metric
        text_pixels = np.sum(binary > 0)
        total_pixels = binary.size
        
        if total_pixels == 0:
            return 0.0
            
        density = (text_pixels / total_pixels) * 100
        
        doc.close()
        return round(density, 2)
        
    except Exception as e:
        # Instead of printing error, return calculated boldness based on font properties
        return 0.0


def analyze_text_differences(pdf_content, page_num=0):
    """
    Analyze all text on a page to find visual differences
    """
    metadata = extract_complete_text_metadata(pdf_content, page_num=page_num)
    
    print("🔍 ENHANCED TEXT ANALYSIS")
    print("=" * 80)
    
    for i, item in enumerate(metadata):
        print(f"\n#{i+1}: '{item['text'][:30]}...'")
        print(f"  Font: {item['clean_font_name']} | Size: {item['font_size']}")
        print(f"  Bold Flag: {item['is_bold_flag']} | Bold Name: {item['is_bold_name']} | FINAL: {item['is_bold_final']}")
        print(f"  Visual Boldness Score: {item['visual_boldness_score']}")
        print(f"  Character Spacing: {item['char_spacing']} | Word Spacing: {item['word_spacing']}")
        print(f"  Flags: {item['font_flags']} | Render Mode: {item['render_mode']}")
        
        # Highlight differences
        if item['visual_boldness_score'] > 2.0:
            print("  🔥 VISUALLY BOLD (thick strokes)")
        if item['font_size'] > 12:
            print("  📏 LARGE TEXT")
        if item['is_bold_final']:
            print("  💪 BOLD DETECTED")
    
    return metadata
