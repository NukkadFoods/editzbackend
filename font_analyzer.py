import fitz
import pdfplumber
import io
import sys

def analyze_pdf_fonts(pdf_content):
    """Detailed font analysis to detect visual boldness differences"""
    
    print('🔍 COMPREHENSIVE FONT ANALYSIS:')
    print('=' * 60)
    
    # PyMuPDF analysis - more detailed
    pdf_doc = fitz.open(stream=pdf_content, filetype='pdf')
    page = pdf_doc[0]
    text_dict = page.get_text('dict')
    
    print('📄 PyMuPDF Detailed Analysis:')
    unique_styles = {}
    
    for block in text_dict['blocks']:
        if 'lines' in block:
            for line in block['lines']:
                for span in line['spans']:
                    if span['text'].strip():
                        # Create a unique style signature
                        style_key = (
                            span['font'],
                            round(span['size'], 1),
                            span['flags'],
                            span.get('color', 0)
                        )
                        
                        if style_key not in unique_styles:
                            unique_styles[style_key] = []
                        unique_styles[style_key].append(span['text'][:30])
    
    # Print unique styles found
    print(f"\n🎨 Found {len(unique_styles)} unique text styles:")
    for i, (style, texts) in enumerate(unique_styles.items(), 1):
        font, size, flags, color = style
        
        # Decode flags
        bold_flag = bool(flags & 2**4)  # 16
        italic_flag = bool(flags & 2**6)  # 64
        
        # Color analysis
        if isinstance(color, int):
            r = (color >> 16) & 255
            g = (color >> 8) & 255
            b = color & 255
            color_desc = f"RGB({r},{g},{b})"
        else:
            color_desc = str(color)
        
        print(f"\n  Style {i}:")
        print(f"    Font: {font}")
        print(f"    Size: {size}")
        print(f"    Flags: {flags} (Bold: {bold_flag}, Italic: {italic_flag})")
        print(f"    Color: {color_desc}")
        print(f"    Sample texts: {', '.join(texts[:3])}")
        
        # Visual weight analysis
        visual_weight = "NORMAL"
        if bold_flag or "bold" in font.lower():
            visual_weight = "BOLD"
        elif size > 12:
            visual_weight = "LARGE (may appear bold)"
        elif flags & 2**0:  # Superscript/subscript
            visual_weight = "MODIFIED"
            
        print(f"    Visual Weight: {visual_weight}")
    
    print('\n' + '=' * 60)
    print('📄 pdfplumber Character-Level Analysis:')
    
    with pdfplumber.open(io.BytesIO(pdf_content)) as plumber_pdf:
        page = plumber_pdf.pages[0]
        chars = page.chars
        
        # Group by font properties
        font_groups = {}
        for char in chars[:50]:  # First 50 chars
            if char['text'].strip():
                key = (char['fontname'], round(char['size'], 1))
                if key not in font_groups:
                    font_groups[key] = []
                font_groups[key].append(char['text'])
        
        print(f"\n🔤 Found {len(font_groups)} character groups:")
        for font_name, size in font_groups.keys():
            chars_sample = ''.join(font_groups[(font_name, size)][:10])
            
            # Enhanced bold detection
            is_bold = any(keyword in font_name.lower() for keyword in ['bold', 'black', 'heavy', 'demi', 'thick'])
            
            print(f"  Font: {font_name:<30} Size: {size:>5.1f} -> {'BOLD' if is_bold else 'REGULAR'}")
            print(f"    Sample: \"{chars_sample}\"")
    
    pdf_doc.close()
    
    print('\n' + '=' * 60)
    print('🎯 DETECTION RECOMMENDATIONS:')
    print("1. Check if font size differences create visual 'boldness'")
    print("2. Look for font weight variations in font names")
    print("3. Analyze font flags for synthetic bold")
    print("4. Consider color intensity differences")

if __name__ == "__main__":
    # This will be called by the main script
    pass
