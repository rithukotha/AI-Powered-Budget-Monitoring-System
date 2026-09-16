# test_upload.py
from ocr_processor import OCRProcessor
import sys
import os

def test_single_image(image_path):
    """Test OCR on a single image"""
    print("=" * 60)
    print("OCR TEST - Single Image Processing")
    print("=" * 60)
    
    # Check if file exists
    if not os.path.exists(image_path):
        print(f"❌ Error: Image file not found: {image_path}")
        return
    
    print(f"\n📁 Testing image: {image_path}")
    print(f"📏 File size: {os.path.getsize(image_path) / 1024:.2f} KB")
    
    # Initialize OCR processor
    print("\n🔄 Initializing OCR processor...")
    processor = OCRProcessor()
    
    # Process the image
    print("🔍 Processing image with OCR...")
    result = processor.process_receipt(image_path)
    
    # Display results
    print("\n" + "-" * 60)
    print("📊 RESULTS:")
    print("-" * 60)
    
    if result['success']:
        print("✅ Status: SUCCESS")
        
        if result.get('extracted_amount'):
            print(f"💰 Amount: ₹{result['extracted_amount']:.2f}")
        else:
            print("💰 Amount: Not detected")
        
        if result.get('predicted_category'):
            print(f"📂 Category: {result['predicted_category']}")
        else:
            print("📂 Category: Not detected")
        
        if result.get('extracted_date'):
            print(f"📅 Date: {result['extracted_date']}")
        else:
            print("📅 Date: Not detected")
        
        print("\n📝 Extracted Text Preview:")
        print("-" * 40)
        print(result.get('extracted_text', 'No text extracted'))
        
    else:
        print(f"❌ Status: FAILED")
        print(f"Message: {result.get('message', 'Unknown error')}")
    
    print("\n" + "=" * 60)

def test_batch_mode():
    """Test multiple images in a folder"""
    print("=" * 60)
    print("OCR TEST - Batch Mode")
    print("=" * 60)
    
    # Check if uploads folder exists
    uploads_dir = "static/uploads"
    if not os.path.exists(uploads_dir):
        print(f"📁 Creating uploads directory: {uploads_dir}")
        os.makedirs(uploads_dir)
    
    # Get all images in uploads folder
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    images = []
    
    for file in os.listdir(uploads_dir):
        if any(file.lower().endswith(ext) for ext in image_extensions):
            images.append(os.path.join(uploads_dir, file))
    
    if not images:
        print("❌ No images found in static/uploads/ folder")
        print("\nPlease add some receipt images to: static/uploads/")
        return
    
    print(f"\n📁 Found {len(images)} image(s) to process:")
    for i, img in enumerate(images, 1):
        print(f"  {i}. {os.path.basename(img)}")
    
    # Process each image
    processor = OCRProcessor()
    
    for i, image_path in enumerate(images, 1):
        print(f"\n{'=' * 50}")
        print(f"Processing Image {i}/{len(images)}: {os.path.basename(image_path)}")
        print(f"{'=' * 50}")
        
        result = processor.process_receipt(image_path)
        
        if result['success']:
            print(f"✅ Success!")
            if result.get('extracted_amount'):
                print(f"   Amount: ₹{result['extracted_amount']:.2f}")
            if result.get('predicted_category'):
                print(f"   Category: {result['predicted_category']}")
            if result.get('extracted_date'):
                print(f"   Date: {result['extracted_date']}")
        else:
            print(f"❌ Failed: {result.get('message', 'Unknown error')}")

def interactive_mode():
    """Interactive mode to test images"""
    while True:
        print("\n" + "=" * 60)
        print("OCR TEST - Interactive Mode")
        print("=" * 60)
        print("\nOptions:")
        print("1. Test a specific image file")
        print("2. Test all images in uploads folder")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == '1':
            image_path = input("\nEnter image file path: ").strip()
            test_single_image(image_path)
        
        elif choice == '2':
            test_batch_mode()
        
        elif choice == '3':
            print("\n👋 Goodbye!")
            break
        
        else:
            print("\n❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    # If command line argument provided
    if len(sys.argv) > 1:
        test_single_image(sys.argv[1])
    else:
        interactive_mode()