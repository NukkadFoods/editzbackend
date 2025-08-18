#!/usr/bin/env python3
"""
Test script to verify the enhanced PDF editing backend works correctly
"""

import requests
import base64
import json

def test_backend():
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Enhanced PDF Backend...")
    
    # Test 1: Health check
    print("\n1️⃣ Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/")
        print(f"✅ Health check: {response.status_code}")
        print(f"📄 Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Test 2: Upload PDF
    print("\n2️⃣ Testing PDF upload...")
    pdf_file_path = "/Users/mahendrabahubali/editz/train-ticket.pdf"
    
    try:
        with open(pdf_file_path, 'rb') as f:
            files = {'file': ('test.pdf', f, 'application/pdf')}
            response = requests.post(f"{base_url}/upload-pdf", files=files)
            
        if response.status_code == 200:
            upload_data = response.json()
            print(f"✅ Upload successful: {upload_data['extractedItems']} items")
            
            # Test 3: Edit text
            print("\n3️⃣ Testing text editing...")
            file_id = upload_data['fileId']
            
            # Find first text item to edit
            text_items = upload_data['textItems']
            if len(text_items) > 0:
                item_to_edit = text_items[0]
                metadata_key = item_to_edit['metadata_key']
                
                edit_request = {
                    "page": 1,
                    "metadata_key": metadata_key,
                    "new_text": "TESTING EDIT",
                    "pdf_data": upload_data['pdfData'],
                    "text_metadata": upload_data['textMetadata']
                }
                
                edit_response = requests.post(
                    f"{base_url}/pdf/{file_id}/edit",
                    json=edit_request
                )
                
                if edit_response.status_code == 200:
                    edit_data = edit_response.json()
                    print(f"✅ Edit successful: {edit_data['message']}")
                    
                    # Test 4: Download PDF
                    print("\n4️⃣ Testing PDF download...")
                    download_request = {
                        "pdf_data": edit_data['modifiedPdfData']
                    }
                    
                    download_response = requests.post(
                        f"{base_url}/pdf/{file_id}/download",
                        json=download_request
                    )
                    
                    if download_response.status_code == 200:
                        print(f"✅ Download successful: {len(download_response.content)} bytes")
                        
                        # Save edited PDF
                        with open("/Users/mahendrabahubali/editz/edited_test.pdf", "wb") as f:
                            f.write(download_response.content)
                        print("📄 Edited PDF saved as edited_test.pdf")
                        
                        # Test 5: Second edit on the same PDF
                        print("\n5️⃣ Testing second edit...")
                        if len(text_items) > 1:
                            second_item = text_items[1]
                            second_metadata_key = second_item['metadata_key']
                            
                            second_edit_request = {
                                "page": 1,
                                "metadata_key": second_metadata_key,
                                "new_text": "SECOND EDIT",
                                "pdf_data": edit_data['modifiedPdfData'],  # Use edited PDF
                                "text_metadata": upload_data['textMetadata']
                            }
                            
                            second_edit_response = requests.post(
                                f"{base_url}/pdf/{file_id}/edit",
                                json=second_edit_request
                            )
                            
                            if second_edit_response.status_code == 200:
                                print("✅ Second edit successful!")
                                print("🎉 Backend is working perfectly!")
                            else:
                                print(f"❌ Second edit failed: {second_edit_response.status_code}")
                                print(f"📄 Error: {second_edit_response.text}")
                        else:
                            print("⚠️ Not enough text items for second edit test")
                    else:
                        print(f"❌ Download failed: {download_response.status_code}")
                        print(f"📄 Error: {download_response.text}")
                else:
                    print(f"❌ Edit failed: {edit_response.status_code}")
                    print(f"📄 Error: {edit_response.text}")
            else:
                print("❌ No text items found in PDF")
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"📄 Error: {response.text}")
            
    except FileNotFoundError:
        print(f"❌ PDF file not found: {pdf_file_path}")
        print("📄 Please upload a PDF through the frontend first")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_backend()
