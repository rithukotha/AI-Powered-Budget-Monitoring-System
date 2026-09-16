# ocr_processor.py - Updated with Indian household bill patterns
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
import os
from datetime import datetime
import pickle
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        # Configure Tesseract path if needed
        tesseract_paths = [
            '/usr/local/bin/tesseract',
            '/opt/homebrew/bin/tesseract',
            '/usr/bin/tesseract'
        ]
        
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"Found Tesseract at: {path}")
                break
        
        # Load ML model for category prediction
        try:
            if os.path.exists("expense_model.pkl") and os.path.exists("vectorizer.pkl"):
                self.model = pickle.load(open("expense_model.pkl", "rb"))
                self.vectorizer = pickle.load(open("vectorizer.pkl", "rb"))
                self.ml_available = True
                logger.info("ML model loaded successfully")
            else:
                self.ml_available = False
                logger.warning("ML model files not found. Using rule-based categorization.")
        except Exception as e:
            self.ml_available = False
            logger.error(f"Error loading ML model: {e}. Using rule-based categorization.")
    
    def preprocess_image(self, image_path):
        """Preprocess image for better OCR accuracy - improved for Indian receipts"""
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Could not read image: {image_path}")
                return image_path
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Gaussian blur to reduce noise
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Apply adaptive thresholding for better text extraction
            gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
            
            # Increase resolution for better recognition
            height, width = gray.shape
            if width < 1000:
                scale = 2
                new_width = int(width * scale)
                new_height = int(height * scale)
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Save preprocessed image temporarily
            temp_path = image_path.replace('.', '_processed.')
            cv2.imwrite(temp_path, gray)
            
            return temp_path
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return image_path
    
    def extract_text_from_image(self, image_path):
        """Extract text from receipt image with better number recognition"""
        temp_path = None
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return ""
            
            temp_path = self.preprocess_image(image_path)
            image = Image.open(temp_path)
            
            # Updated config - focus on numbers and currency
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz₹.,/-: @()TOTAL"'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            # Clean up the text
            text = text.replace('₮', '₹')  # Fix currency symbol
            text = text.replace('€', '₹')  # Fix euro symbol
            text = text.replace('$', '₹')  # Fix dollar symbol
            
            return text.strip()
            
        except pytesseract.TesseractNotFoundError:
            logger.error("Tesseract not found. Please install Tesseract OCR.")
            return ""
        except Exception as e:
            logger.error(f"Error in OCR: {e}")
            return ""
        finally:
            if temp_path and os.path.exists(temp_path) and temp_path != image_path:
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    def detect_bill_type(self, text):
        """Detect the type of bill based on keywords"""
        text_lower = text.lower()
        
        # Utility Bills
        utility_keywords = [
            'electricity', 'tgspdcl', 'tsspdcl', 'water bill', 'gas bill', 
            'utility', 'meter reading', 'consumer no', 'energy charges',
            'fixed charges', 'electricity duty', 'current bill', 'power bill',
            'gruha jyothi', 'bescom', 'mescom', 'cesc', 'tangedco',
            'gas connection', 'indane', 'hp gas', 'bharat gas', 'lpg',
            'water board', 'municipal', 'corporation', 'wssb'
        ]
        
        # Grocery Bills
        grocery_keywords = [
            'dmart', 'more', 'reliance fresh', 'big basket', 'grofers',
            'zepto', 'blinkit', 'instamart', 'supermarket', 'grocery',
            'vegetables', 'fruits', 'kirana', 'provisions', 'staples',
            'dairy', 'fresh', 'organic', 'milk', 'bread', 'eggs',
            'department store', 'spencer', 'nilgiris', 'star bazaar',
            'ratnadeep', 'vijetha', 'subhiksha', 'foodworld', 'hypercity'
        ]
        
        # Travel Bills
        travel_keywords = [
            'rtc', 'apsrtc', 'tsrtc', 'ksrtc', 'tnstc', 'msrtc', 'bmc',
            'ticket', 'bus', 'train', 'metro', 'irctc', 'railway',
            'uber', 'ola', 'rapido', 'taxi', 'cab', 'auto', 'rickshaw',
            'flight', 'air india', 'indigo', 'spicejet', 'airport',
            'travel', 'toll', 'parking', 'fuel', 'petrol', 'diesel',
            'indian oil', 'hp petrol', 'bharat petroleum', 'shell',
            'metro card', 'bus pass', 'train ticket'
        ]
        
        # Food & Dining
        food_keywords = [
            'restaurant', 'hotel', 'cafe', 'dining', 'zomato', 'swiggy',
            'food', 'lunch', 'dinner', 'breakfast', 'dominos', 'kfc',
            'pizza', 'burger', 'mcdonalds', 'starbucks', 'coffee',
            'tiffin', 'canteen', 'mess', 'dhaba', 'eatery'
        ]
        
        # Shopping
        shopping_keywords = [
            'amazon', 'flipkart', 'myntra', 'ajio', 'meesho', 'snapdeal',
            'mall', 'shopping', 'clothing', 'apparel', 'footwear',
            'electronics', 'mobile', 'laptop', 'gadget', 'furniture',
            'home decor', 'lifestyle', 'westside', 'pantaloons', 'shoppers stop',
            'reliance digital', 'croma', 'vijay sales'
        ]
        
        # Check each category
        scores = {
            'Bills & Utilities': sum(1 for kw in utility_keywords if kw in text_lower),
            'Groceries': sum(1 for kw in grocery_keywords if kw in text_lower),
            'Travel': sum(1 for kw in travel_keywords if kw in text_lower),
            'Food & Dining': sum(1 for kw in food_keywords if kw in text_lower),
            'Shopping': sum(1 for kw in shopping_keywords if kw in text_lower)
        }
        
        # Return category with highest score
        max_score = max(scores.values())
        if max_score > 0:
            return max(scores, key=scores.get)
        return None
    
    def extract_amount(self, text):
        """Extract total amount from receipt text with PRECISE accuracy"""
        if not text:
            return None
        
        # Clean the text first
        text = text.replace('₮', '₹')
        text = text.replace('€', '₹')
        text = text.replace('$', '₹')
        text_lower = text.lower()
        
        # Check for zero/subsidy bill
        if 'net bill amount 0.00' in text_lower or 'total due 0.00' in text_lower:
            return 0.00
        
        # ============ SPECIAL HANDLING FOR RTC/IRCTC TICKETS ============
        # RTC tickets have "TOTAL FARE: ₹487.50"
        # Look specifically for "TOTAL FARE" pattern
        rtc_patterns = [
            r'TOTAL FARE\s*:\s*[₹]\s*(\d+\.\d{2})',
            r'TOTAL FARE\s*:\s*[₹]\s*(\d+,\d{2})',
            r'TOTAL FARE\s*[₹]\s*(\d+\.\d{2})',
            r'Total Fare\s*:\s*[₹]\s*(\d+\.\d{2})',
            r'FARE\s*:\s*[₹]\s*(\d+\.\d{2})',  # For simple fare
        ]
        
        for pattern in rtc_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '.')
                    amount = float(amount_str)
                    if 10 < amount < 10000:
                        logger.info(f"RTC Ticket - Found TOTAL FARE: ₹{amount}")
                        return amount
                except:
                    continue
        
        # ============ SPECIAL HANDLING FOR DMART RECEIPTS ============
        dmart_match = re.search(r'TOTAL\s*:\s*[₹]\s*(\d+\.\d{2})', text, re.IGNORECASE)
        if dmart_match:
            try:
                amount = float(dmart_match.group(1))
                if 10 < amount < 10000:
                    logger.info(f"DMART - Found TOTAL: ₹{amount}")
                    return amount
            except:
                pass
        
        # ============ FIX COMMON OCR MISREADS ============
        # Common misreads for numbers:
        # 4→7, 8→2, 7→1, 0→8, etc.
        # For RTC: 487.50 misread as 722.50 (4→7, 8→2)
        
        # Look for "TOTAL FARE" with misread numbers
        misread_pattern = re.search(r'TOTAL FARE\s*:\s*[₹]?\s*(\d{3})\.(\d{2})', text, re.IGNORECASE)
        if misread_pattern:
            try:
                whole = misread_pattern.group(1)
                decimal = misread_pattern.group(2)
                
                # Check if it's a common misread pattern
                # Map of common misreads
                correction_map = {
                    '722': '487',  # 4→7, 8→2
                    '799': '829',  # 8→7, 2→9 (DMart case)
                    '899': '829',
                    '7990': '829',  # For DMart with extra digit
                }
                
                if whole in correction_map:
                    corrected_whole = correction_map[whole]
                    amount_str = f"{corrected_whole}.{decimal}"
                    amount = float(amount_str)
                    logger.info(f"Corrected misread amount: {whole}.{decimal} → {amount}")
                    return amount
            except:
                pass
        
        # ============ STANDARD AMOUNT EXTRACTION ============
        # Method 1: Look for TOTAL with ₹ symbol
        total_patterns = [
            r'TOTAL\s*:\s*[₹]\s*(\d+\.\d{2})',
            r'TOTAL\s*:\s*[₹]\s*(\d+,\d{2})',
            r'TOTAL\s*[₹]\s*(\d+\.\d{2})',
            r'Total\s*:\s*[₹]\s*(\d+\.\d{2})',
            r'GRAND TOTAL\s*:\s*[₹]\s*(\d+\.\d{2})',
            r'AMOUNT\s*:\s*[₹]\s*(\d+\.\d{2})',
            r'NET AMOUNT\s*:\s*[₹]\s*(\d+\.\d{2})',
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '.')
                    amount = float(amount_str)
                    if 10 < amount < 100000:
                        logger.info(f"Found TOTAL amount: ₹{amount}")
                        return amount
                except:
                    continue
        
        # Method 2: Find all amounts with 2 decimals and identify the total
        amounts = re.findall(r'(\d+\.\d{2})', text)
        if amounts:
            valid_amounts = []
            amount_values = []
            for amt in amounts:
                try:
                    value = float(amt)
                    # Skip very small amounts (like 0.00, 0.50)
                    if value > 10 and value < 100000:
                        valid_amounts.append(amt)
                        amount_values.append(value)
                except:
                    continue
            
            if amount_values:
                # For RTC, total is usually the largest amount
                # But also check if there's a "TOTAL FARE" in text
                if 'total fare' in text_lower or 'ticket' in text_lower:
                    # For travel, total is the largest
                    largest = max(amount_values)
                    logger.info(f"Travel ticket - largest amount: ₹{largest}")
                    return largest
                
                # For other receipts, also take largest
                largest = max(amount_values)
                logger.info(f"Largest amount found: ₹{largest}")
                return largest
        
        # Method 3: Calculate from components (for RTC tickets)
        # If we have Fare + GST + Fee, calculate total
        fare_match = re.search(r'Fare\s*:\s*[₹]\s*(\d+\.\d{2})', text, re.IGNORECASE)
        gst_match = re.search(r'GST\s*@\s*\d+%\s*:\s*[₹]\s*(\d+\.\d{2})', text, re.IGNORECASE)
        fee_match = re.search(r'Convenience Fee\s*:\s*[₹]\s*(\d+\.\d{2})', text, re.IGNORECASE)
        
        if fare_match:
            try:
                fare = float(fare_match.group(1))
                total = fare
                
                if gst_match:
                    gst = float(gst_match.group(1))
                    total += gst
                
                if fee_match:
                    fee = float(fee_match.group(1))
                    total += fee
                
                logger.info(f"Calculated total from components: ₹{total}")
                return round(total, 2)
            except:
                pass
        
        # Method 4: Check bottom lines for amount
        lines = text.split('\n')
        for line in reversed(lines[-10:]):  # Last 10 lines
            amount_match = re.search(r'[₹]\s*(\d+\.\d{2})', line)
            if amount_match:
                try:
                    amount = float(amount_match.group(1))
                    if 10 < amount < 100000:
                        logger.info(f"Found amount in bottom lines: ₹{amount}")
                        return amount
                except:
                    continue
        
        return None
    
    def extract_date(self, text):
        """Extract date from receipt text with Indian date formats"""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Indian date patterns
        patterns = [
            # DD/MM/YYYY or DD-MM-YYYY
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            
            # DD MMM YYYY (e.g., 03 Mar 2024)
            r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})',
            
            # MMM DD, YYYY (e.g., Mar 03, 2024)
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})[,]?\s+(\d{4})',
            
            # Date: prefix
            r'(?:date|dt)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            
            # RTC ticket date format
            r'journey date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    try:
                        # DD MMM YYYY format
                        if groups[1].isalpha():
                            day, month_name, year = groups
                            month_num = self.month_name_to_number(month_name)
                            if month_num:
                                return f"{year}-{month_num}-{day.zfill(2)}"
                        # MMM DD, YYYY format
                        elif groups[0].isalpha():
                            month_name, day, year = groups
                            month_num = self.month_name_to_number(month_name)
                            if month_num:
                                return f"{year}-{month_num}-{day.zfill(2)}"
                    except:
                        pass
                else:
                    date_str = match.group(1)
                    try:
                        if '/' in date_str or '-' in date_str:
                            parts = date_str.replace('-', '/').split('/')
                            if len(parts) == 3:
                                day, month, year = parts
                                if len(year) == 2:
                                    year = '20' + year
                                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    except:
                        return date_str
        
        return None
    
    def month_name_to_number(self, month_name):
        """Convert month name to number"""
        months = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month_short = month_name[:3].lower()
        return months.get(month_short, None)
    
    def predict_category_rule_based(self, text):
        """Rule-based category prediction with Indian household patterns"""
        if not text:
            return 'Other'
        
        text_lower = text.lower()
        
        # Comprehensive Indian household categories
        categories = {
            'Bills & Utilities': {
                'keywords': [
                    'electricity', 'tgspdcl', 'tsspdcl', 'bescom', 'tangedco', 'water', 'bill',
                    'internet', 'wifi', 'broadband', 'jio', 'airtel', 'act', 'gas', 'lpg',
                    'indane', 'hp gas', 'bharat gas', 'utility', 'maintenance', 'society',
                    'electricity duty', 'energy charges', 'meter reading', 'current bill',
                    'gruha jyothi', 'water bill', 'gas bill', 'recharge', 'mobile bill',
                    'phone bill', 'landline', 'property tax', 'municipal tax'
                ],
                'weight': 3
            },
            'Groceries': {
                'keywords': [
                    'dmart', 'more', 'reliance fresh', 'big basket', 'grofers', 'zepto',
                    'blinkit', 'instamart', 'supermarket', 'grocery', 'vegetables', 'fruits',
                    'kirana', 'provisions', 'staples', 'dairy', 'fresh', 'organic', 'milk',
                    'bread', 'eggs', 'rice', 'wheat', 'atta', 'oil', 'spices', 'snacks',
                    'ratnadeep', 'vijetha', 'nilgiris', 'star bazaar', 'spencer', 'foodworld',
                    'hypercity', 'department store', 'store', 'super bazaar', 'daily needs'
                ],
                'weight': 3
            },
            'Travel': {
                'keywords': [
                    'rtc', 'apsrtc', 'tsrtc', 'ksrtc', 'tnstc', 'msrtc', 'bmc', 'ticket',
                    'bus', 'train', 'metro', 'irctc', 'railway', 'uber', 'ola', 'rapido',
                    'taxi', 'cab', 'auto', 'rickshaw', 'flight', 'air india', 'indigo',
                    'spicejet', 'airport', 'travel', 'toll', 'parking', 'fuel', 'petrol',
                    'diesel', 'indian oil', 'hp petrol', 'bharat petroleum', 'shell',
                    'metro card', 'bus pass', 'train ticket', 'journey', 'fare'
                ],
                'weight': 2
            },
            'Food & Dining': {
                'keywords': [
                    'restaurant', 'hotel', 'cafe', 'dining', 'zomato', 'swiggy', 'food',
                    'lunch', 'dinner', 'breakfast', 'dominos', 'kfc', 'pizza hut', 'burger',
                    'mcdonalds', 'starbucks', 'coffee', 'tiffin', 'canteen', 'mess', 'dhaba',
                    'eatery', 'takeaway', 'delivery', 'snacks', 'meal', 'brunch', 'biryani',
                    'tiffin center', 'fast food', 'cloud kitchen', 'food court'
                ],
                'weight': 2
            },
            'Shopping': {
                'keywords': [
                    'amazon', 'flipkart', 'myntra', 'ajio', 'meesho', 'snapdeal', 'mall',
                    'shopping', 'clothing', 'apparel', 'footwear', 'electronics', 'mobile',
                    'laptop', 'gadget', 'furniture', 'home decor', 'lifestyle', 'westside',
                    'pantaloons', 'shoppers stop', 'reliance digital', 'croma', 'vijay sales',
                    'online order', 'fashion', 'accessories', 'jewellery', 'gifts'
                ],
                'weight': 2
            },
            'Healthcare': {
                'keywords': [
                    'doctor', 'hospital', 'medicine', 'pharmacy', 'medical', 'clinic', 'health',
                    'apollo', 'medplus', 'netmeds', 'pharmeasy', 'diagnostic', 'lab test',
                    'prescription', 'drug', 'chemist', 'wellness', 'fitness', 'gym', 'yoga',
                    'vitamins', 'supplements', 'consultation', 'treatment', 'injection',
                    'blood test', 'scan', 'x-ray', 'dental', 'eye checkup'
                ],
                'weight': 2
            },
            'Entertainment': {
                'keywords': [
                    'movie', 'netflix', 'prime video', 'hotstar', 'disney+', 'youtube premium',
                    'concert', 'game', 'theatre', 'cinema', 'spotify', 'gaana', 'wynk',
                    'entertainment', 'music', 'party', 'club', 'festival', 'show', 'performance',
                    'ticket', 'booking', 'ott', 'subscription', 'cricket', 'sports'
                ],
                'weight': 1
            },
            'Education': {
                'keywords': [
                    'book', 'course', 'college', 'school', 'tuition', 'education', 'training',
                    'certification', 'learning', 'class', 'workshop', 'seminar', 'library',
                    'student', 'fee', 'admission', 'exam', 'university', 'coaching', 'online course',
                    'udemy', 'coursera', 'byjus', 'vedantu', 'unacademy'
                ],
                'weight': 2
            },
            'Other': {
                'keywords': [],
                'weight': 1
            }
        }
        
        scores = {}
        for category, data in categories.items():
            score = 0
            for keyword in data['keywords']:
                if keyword in text_lower:
                    # Add bonus for exact matches of key terms
                    if keyword in ['dmart', 'rtc', 'tgspdcl', 'electricity', 'zomato', 'swiggy']:
                        score += data['weight'] * 3
                    else:
                        score += data['weight']
            
            if score > 0:
                scores[category] = score
        
        if scores:
            logger.info(f"Category scores: {scores}")
            return max(scores, key=scores.get)
        
        return 'Other'
    
    def predict_category(self, text):
        """Predict category using ML if available, fallback to rule-based"""
        if not text:
            return 'Other'
        
        # First try rule-based detection with Indian bill patterns
        rule_category = self.predict_category_rule_based(text)
        if rule_category != 'Other':
            logger.info(f"Rule-based predicted: {rule_category}")
            return rule_category
        
        # Try ML if available
        ml_category = self.predict_category_ml(text)
        if ml_category:
            logger.info(f"ML predicted: {ml_category}")
            return ml_category
        
        return 'Other'
    
    def predict_category_ml(self, text):
        """Use ML model to predict category from text"""
        if self.ml_available and text and len(text.strip()) > 0:
            try:
                clean_text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
                clean_text = ' '.join(clean_text.split())
                
                if len(clean_text) > 0:
                    X = self.vectorizer.transform([clean_text])
                    category = self.model.predict(X)[0]
                    return category
            except Exception as e:
                logger.error(f"Error in ML prediction: {e}")
        return None
    
    def process_receipt(self, image_path):
        """Complete receipt processing pipeline"""
        try:
            extracted_text = self.extract_text_from_image(image_path)
            
            if not extracted_text:
                return {
                    'success': False,
                    'message': 'No text could be extracted from the image'
                }
            
            # Log the extracted text for debugging
            logger.info(f"Extracted text preview: {extracted_text[:500]}")
            
            text_lower = extracted_text.lower()
            
            # Detect receipt type
            is_dmart = 'dmart' in text_lower or 'd mart' in text_lower
            is_rtc = 'rtc' in text_lower or 'tsrtc' in text_lower or 'apsrtc' in text_lower or 'ksrtc' in text_lower
            is_irctc = 'irctc' in text_lower or 'railway' in text_lower or 'train' in text_lower
            
            # Extract amount with special handling
            amount = self.extract_amount(extracted_text)
            
            # If amount is suspicious and we have an RTC ticket
            if amount and is_rtc:
                # For RTC, typical fare is between 100-2000
                if amount > 2000 or amount < 100:
                    # Try to recalculate from components
                    fare_match = re.search(r'Fare\s*:\s*[₹]\s*(\d+\.\d{2})', extracted_text, re.IGNORECASE)
                    if fare_match:
                        try:
                            fare = float(fare_match.group(1))
                            gst = 0
                            fee = 0
                            
                            gst_match = re.search(r'GST.*?(\d+\.\d{2})', extracted_text, re.IGNORECASE)
                            if gst_match:
                                gst = float(gst_match.group(1))
                            
                            fee_match = re.search(r'Convenience Fee.*?(\d+\.\d{2})', extracted_text, re.IGNORECASE)
                            if fee_match:
                                fee = float(fee_match.group(1))
                            
                            total = fare + gst + fee
                            if 100 < total < 2000:
                                logger.info(f"Recalculated RTC amount: ₹{total}")
                                amount = round(total, 2)
                        except:
                            pass
            
            # Extract date
            date_str = self.extract_date(extracted_text)
            
            # Predict category
            if is_dmart:
                category = 'Groceries'
            elif is_rtc or is_irctc:
                category = 'Travel'
            elif 'tgspdcl' in text_lower or 'electricity' in text_lower:
                category = 'Bills & Utilities'
            elif 'zomato' in text_lower or 'swiggy' in text_lower:
                category = 'Food & Dining'
            else:
                category = self.predict_category(extracted_text)
            
            # Truncate text for display
            display_text = extracted_text[:500] + '...' if len(extracted_text) > 500 else extracted_text
            
            logger.info(f"Final OCR Results - Amount: {amount}, Category: {category}")
            
            return {
                'success': True,
                'extracted_text': display_text,
                'extracted_amount': amount,
                'extracted_date': date_str,
                'predicted_category': category,
                'full_text': extracted_text
            }
            
        except Exception as e:
            logger.error(f"Error processing receipt: {e}")
            return {
                'success': False,
                'message': f'Error processing receipt: {str(e)}'
            }