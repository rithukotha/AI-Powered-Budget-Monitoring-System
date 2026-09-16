# test_ocr.py
from ocr_processor import OCRProcessor
import sys
import os

def test_ocr():
    print("=" * 50)
    print("Testing OCR Processor")
    print("=" * 50)
    
    try:
        processor = OCRProcessor()
        
        # Test with a sample receipt text
        sample_receipt = """
        KFC Restaurant
        Date: 15/03/2024
        Time: 19:30
        
        2x Zinger Burger     ₹350.00
        1x Pepsi             ₹60.00
        1x Fries             ₹90.00
        
        Subtotal:           ₹500.00
        Tax (10%):          ₹50.00
        Total:              ₹550.00
        
        Thank you for visiting!
        """
        
        print("\n1. Testing text-based extraction:")
        print("-" * 30)
        
        # Test amount extraction
        amount = processor.extract_amount(sample_receipt)
        print(f"Extracted amount: ₹{amount if amount else 'Not found'}")
        
        # Test category prediction
        category = processor.predict_category(sample_receipt)
        print(f"Predicted category: {category}")
        
        # Test date extraction
        date = processor.extract_date(sample_receipt)
        print(f"Extracted date: {date if date else 'Not found'}")
        
        # Test with an image file if available
        print("\n2. Testing image-based extraction:")
        print("-" * 30)
        
        # Check if there's a receipt image in the uploads folder
        test_image = "static/uploads/test_receipt.jpg"
        if os.path.exists(test_image):
            result = processor.process_receipt(test_image)
            if result['success']:
                print(f"Image processed successfully!")
                print(f"Extracted amount: ₹{result['extracted_amount'] if result['extracted_amount'] else 'Not found'}")
                print(f"Predicted category: {result['predicted_category']}")
                print(f"Extracted date: {result['extracted_date'] if result['extracted_date'] else 'Not found'}")
                print(f"\nExtracted text preview:\n{result['extracted_text'][:200]}...")
            else:
                print(f"Could not process image: {result.get('message', 'Unknown error')}")
        else:
            print("No test receipt image found. Skipping image test.")
            print("To test with an image, place a receipt image at: static/uploads/test_receipt.jpg")
        
        print("\n" + "=" * 50)
        print("OCR Test Complete!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ocr()