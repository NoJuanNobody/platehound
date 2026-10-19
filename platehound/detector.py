import re
from typing import Optional, Dict, Any, Tuple

class FloridaPlateDetector:
    """
    Florida License Plate Detector & Validator.
    Handles raw string normalization, regex validation for standard & specialty FL plate formats,
    and modular integration with OCR/YOLO ALPR outputs.
    """
    
    # Common Florida Formats:
    # 1. AAA B00 (3 letters, 1 space/dot/dash, 1 letter, 2 digits)
    # 2. 00A BCD (2 digits, 1 letter, 3 letters)
    # 3. AAA 00A (3 letters, 2 digits, 1 letter)
    # 4. Standard 6/7 alphanum patterns
    FL_PATTERNS = [
        re.compile(r"^[A-Z]{3}\s?[A-Z0-9]{3,4}$"),  # General 6-7 character plates
        re.compile(r"^[0-9]{2}[A-Z]{1}\s?[A-Z0-9]{3}$"), # FL Truck / Standard
        re.compile(r"^[A-Z0-9]{1,7}$")               # Vanity / Specialty plates
    ]

    @staticmethod
    def clean_plate_string(raw: str) -> str:
        """Strip non-alphanumeric characters, remove state prefix if present, and uppercase."""
        if not raw:
            return ""
        cleaned = raw.strip().upper()
        # Remove typical prefixes like 'FL-', 'FL ', 'FLORIDA'
        cleaned = re.sub(r'^(FL|FLORIDA)[\s\-_:]*', '', cleaned)
        # Strip internal hyphens or weird OCR punctuation
        cleaned = re.sub(r'[^A-Z0-9]', '', cleaned)
        return cleaned

    def validate_florida_plate(self, plate: str) -> Tuple[bool, float]:
        """
        Validates if plate matches plausible Florida schema.
        Returns (is_valid, confidence_score).
        """
        cleaned = self.clean_plate_string(plate)
        if not (1 <= len(cleaned) <= 7):
            return False, 0.0

        for pattern in self.FL_PATTERNS:
            if pattern.match(cleaned):
                # Standard FL plates are typically 6-7 characters
                score = 0.95 if len(cleaned) in [6, 7] else 0.80
                return True, score

        return True, 0.50

    def parse_alpr_result(self, raw_input: str, model_confidence: float = 0.92) -> Dict[str, Any]:
        """
        Takes raw OCR/YOLO detection output and normalizes it.
        """
        plate = self.clean_plate_string(raw_input)
        valid, fl_score = self.validate_florida_plate(plate)
        combined_confidence = round(model_confidence * fl_score, 3)

        return {
            "raw_input": raw_input,
            "plate": plate,
            "state": "FL",
            "is_valid_format": valid,
            "confidence": combined_confidence,
            "detector": "YOLO-PlateDet-v8 + Tesseract-OCR"
        }
