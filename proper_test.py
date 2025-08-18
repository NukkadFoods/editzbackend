#!/usr/bin/env python3
"""
Proper Multi-Edit Backend Test
Tests if backend can handle multiple consecutive PDF edits
"""
import subprocess
import threading
import time
import requests
import json
import base64

# Start backend server in background
def start_server():
    """Start the FastAPI server"""
    subprocess.run(['python3', 'index_advanced.py'], cwd='/Users/mahendrabahubali/editz/backend')

# Start server in background thread
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# Wait for server to start
print("⏳ Waiting for server to start...")
time.sleep(3)

# Test configuration
BASE_URL = "http://localhost:8000"
PDF_PATH = "/Users/mahendrabahubali/editz/backend/test_sample.pdf"

def test_multiple_edits():
    """Test multiple consecutive edits on the same PDF"""
    try:
        # Step 1: Upload PDF
        print("\n🚀 STEP 1: Uploading PDF...")
        with open(PDF_PATH, 'rb') as f:
            files = {'file': ('test.pdf', f, 'application/pdf')}
            upload_response = requests.post(f"{BASE_URL}/upload-pdf", files=files)
        
        if upload_response.status_code != 200:
            print(f"❌ Upload failed: {upload_response.status_code}")
            return False
            
        upload_data = upload_response.json()
        file_id = upload_data['fileId']
        print(f"✅ Upload successful! File ID: {file_id}")
        print(f"📊 Found {len(upload_data['textItems'])} text items")
        
        # Store PDF data and metadata for edits
        pdf_data = upload_data['pdfData']
        text_metadata = upload_data['textMetadata']
        
        # Find some editable text items
        text_items = upload_data['textItems']
        edit_targets = []
        
        # For testing multiple edits, we'll edit the same item multiple times
        if text_items:
            item = text_items[0]  # Use the first item
            for i in range(3):  # Test 3 consecutive edits on same item
                edit_targets.append((0, item))  # Same item, multiple times
        
        print(f"\n🎯 Selected {len(edit_targets)} items for editing:")
        for i, (idx, item) in enumerate(edit_targets):
            print(f"  {i+1}. Item {idx}: '{item['text']}' on page {item['page']}")
        
        # Step 2: Perform multiple edits
        successful_edits = 0
        
        for edit_num, (item_idx, item) in enumerate(edit_targets, 1):
            print(f"\n🔄 EDIT {edit_num}: Editing item {item_idx}")
            print(f"   Original: '{item['text']}'")
            
            new_text = f"EDITED_{edit_num}_TEST"
            edit_payload = {
                "page": item['page'],
                "metadata_key": f"text_item_{item_idx}",
                "new_text": new_text,
                "pdf_data": pdf_data,
                "text_metadata": text_metadata
            }
            
            print(f"   New text: '{new_text}'")
            
            # Make edit request
            edit_response = requests.post(
                f"{BASE_URL}/pdf/{file_id}/edit",
                json=edit_payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if edit_response.status_code == 200:
                print(f"   ✅ Edit {edit_num} successful!")
                successful_edits += 1
                
                # Update PDF data for next edit
                edit_result = edit_response.json()
                if 'editedPdfData' in edit_result:
                    pdf_data = edit_result['editedPdfData']
                
                # Optional: Download and verify after each edit
                download_payload = {"pdf_data": pdf_data}
                download_response = requests.post(f"{BASE_URL}/pdf/{file_id}/download", json=download_payload)
                if download_response.status_code == 200:
                    print(f"   ✅ Download after edit {edit_num} successful! ({len(download_response.content)} bytes)")
                else:
                    print(f"   ⚠️ Download after edit {edit_num} failed: {download_response.status_code}")
            else:
                print(f"   ❌ Edit {edit_num} failed: {edit_response.status_code}")
                try:
                    error_data = edit_response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error text: {edit_response.text}")
        
        # Step 3: Final download test
        print(f"\n📥 FINAL DOWNLOAD TEST:")
        final_download_payload = {"pdf_data": pdf_data}
        final_download = requests.post(f"{BASE_URL}/pdf/{file_id}/download", json=final_download_payload)
        
        if final_download.status_code == 200:
            print(f"✅ Final download successful! ({len(final_download.content)} bytes)")
            
            # Save the edited PDF
            with open('/Users/mahendrabahubali/editz/backend/test_output_multiple_edits.pdf', 'wb') as f:
                f.write(final_download.content)
            print("✅ Saved edited PDF as test_output_multiple_edits.pdf")
            
        else:
            print(f"❌ Final download failed: {final_download.status_code}")
        
        # Summary
        print(f"\n📊 MULTI-EDIT TEST SUMMARY:")
        print(f"   Successful edits: {successful_edits}/{len(edit_targets)}")
        print(f"   Final download: {'SUCCESS' if final_download.status_code == 200 else 'FAILED'}")
        
        return successful_edits == len(edit_targets) and final_download.status_code == 200
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 MULTI-EDIT BACKEND TEST")
    print("=" * 50)
    
    success = test_multiple_edits()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED! Backend can handle multiple edits!")
    else:
        print("❌ Some tests failed. Check logs above.")
