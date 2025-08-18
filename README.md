# PDF Editor Backend - Advanced

## 🚀 Features

- **Multi-Page Support**: Process all pages of PDF documents
- **Intelligent Text Alignment**: Smart detection of centered, left-aligned, and tabular text
- **Station Name Recognition**: Automatic detection and proper centering of location names
- **Enhanced Font Matching**: Precise font family and weight matching
- **Visual Boldness Detection**: Advanced boldness analysis beyond font flags
- **Color Preservation**: RGB color extraction and preservation during edits
- **Character & Word Spacing**: Precise spacing control for natural text appearance

## 🎯 Intelligent Alignment System

### Station Name Detection
- Detects patterns like "SATNA (STA)", "NEW DELHI (NDLS)"
- Maintains center position when text length changes
- Prevents unwanted page-center alignment

### Context-Aware Positioning
- **Left-aligned text**: Expands to the right
- **Centered text**: Maintains center position
- **List items**: Preserves bullet/number alignment
- **Tabular data**: Maintains column structure

### Visual Boldness Analysis
- Analyzes text rendering for true boldness
- Combines font flags, name analysis, and visual inspection
- Preserves original text weight accurately

## 🔧 API Endpoints

### Upload PDF
```
POST /upload-pdf
Content-Type: multipart/form-data

Returns: {
  success: boolean,
  fileId: string,
  textItems: TextItem[],
  pdfData: string,
  textMetadata: object,
  extractedItems: number,
  embeddedFonts: number
}
```

### Edit Text
```
POST /pdf/{fileId}/edit
Content-Type: application/json

Body: {
  page: number,
  metadata_key: string,
  new_text: string,
  pdf_data: string,
  text_metadata: object
}
```

### Download PDF
```
POST /pdf/{fileId}/download
Content-Type: application/json

Body: {
  pdf_data: string
}
```

### Get Page Text
```
GET /pdf/{fileId}/pages/{pageNum}/text

Returns: {
  success: boolean,
  textItems: TextItem[],
  page: number
}
```

## 🚀 Deployment

### Vercel Deployment
1. Connect this repository to Vercel
2. Configure environment variables:
   - `FRONTEND_URL`: Your frontend domain
3. Deploy automatically on push to main branch

### Local Development
```bash
pip install -r requirements.txt
python3 index_advanced.py
```

Server runs on `http://localhost:8000`

## 📦 Dependencies

- FastAPI - Modern web framework
- PyMuPDF (fitz) - PDF processing
- Uvicorn - ASGI server
- python-multipart - File upload support

## 🔒 CORS Configuration

Backend accepts requests from:
- `http://localhost:3000` (development)
- `https://*.vercel.app` (production)
- Environment variable `FRONTEND_URL`

## 🎨 Backend Version
**v3.0.0** - Advanced PDF Editor with Intelligent Alignment

### Features Added in v3.0:
- Multi-page text extraction and editing
- Smart alignment detection and preservation
- Station name pattern recognition
- Enhanced font weight matching
- Character spacing control
- Visual boldness analysis
- RGB color preservation fixes

## 📝 Usage Example

```javascript
// Upload PDF
const formData = new FormData();
formData.append('file', pdfFile);
const response = await fetch('/upload-pdf', {
  method: 'POST',
  body: formData
});

// Edit text with intelligent alignment
const editResponse = await fetch(`/pdf/${fileId}/edit`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    page: 1,
    metadata_key: 'text_item_5',
    new_text: 'RANI KAMLAPATI (RKMP)',
    pdf_data: pdfDataBase64,
    text_metadata: metadata
  })
});
```

## 🐛 Debugging

Backend provides detailed logging:
- Text context analysis
- Station name detection
- Alignment strategy selection
- Font matching decisions
- Color extraction details

Enable verbose logging by checking server console output.
