"""
Unit tests for Greek Transliteration Service
Tests the automatic conversion of English letters to Greek
"""
import pytest
from django.test import TestCase
from core.services.greek_transliteration_service import GreekTransliterationService


class TestGreekTransliterationService(TestCase):
    """Test the GreekTransliterationService"""

    def test_transliterate_basic_word(self):
        """Test transliteration of basic Greek words"""
        # Single words
        self.assertEqual(GreekTransliterationService.transliterate("DHMOS"), "ΔΗΜΟΣ")
        self.assertEqual(GreekTransliterationService.transliterate("YPOURGEIA"), "ΥΠΟΥΡΓΕΙΑ")
        self.assertEqual(GreekTransliterationService.transliterate("PERIFEREIA"), "ΠΕΡΙΦΕΡΕΙΑ")
    
    def test_transliterate_with_spaces(self):
        """Test transliteration with multiple words"""
        result = GreekTransliterationService.transliterate("DHMOS ATHINON")
        self.assertEqual(result, "ΔΗΜΟΣ ΑΘΙΝΟΝ")
    
    def test_transliterate_lowercase(self):
        """Test that lowercase input is transliterated preserving case"""
        self.assertEqual(GreekTransliterationService.transliterate("dhmos"), "δημοσ")
        self.assertEqual(GreekTransliterationService.transliterate("ypourgeia"), "υπουργεια")
    
    def test_transliterate_mixed_case(self):
        """Test mixed case input preserves case"""
        self.assertEqual(GreekTransliterationService.transliterate("DhMoS"), "ΔηΜοΣ")
    
    def test_transliterate_with_numbers(self):
        """Test that numbers and special characters are preserved"""
        result = GreekTransliterationService.transliterate("DHMOS 123")
        self.assertEqual(result, "ΔΗΜΟΣ 123")
    
    def test_transliterate_special_combinations(self):
        """Test two-letter combinations like TH, CH, PH, PS"""
        # TH combination
        result = GreekTransliterationService.transliterate("THESSA")
        # Should contain Θ for TH
        self.assertIn("Θ", result)
        
        # PH combination
        result = GreekTransliterationService.transliterate("PHOS")
        self.assertIn("Φ", result)
        
        # CH combination
        result = GreekTransliterationService.transliterate("CHANIA")
        self.assertIn("Χ", result)
    
    def test_transliterate_empty_string(self):
        """Test with empty string"""
        self.assertEqual(GreekTransliterationService.transliterate(""), "")
    
    def test_transliterate_already_greek(self):
        """Test with already Greek text - should remain unchanged"""
        greek_text = "ΔΗΜΟΣ"
        result = GreekTransliterationService.transliterate(greek_text)
        # Should remain unchanged since there are no translatable Latin characters
        self.assertEqual(result, greek_text)
    
    def test_transliterate_with_preserve_original(self):
        """Test preserve_original flag"""
        # When preserve_original=True, should return original
        result = GreekTransliterationService.transliterate("DHMOS", preserve_original=True)
        self.assertEqual(result, "DHMOS")
    
    def test_needs_transliteration_detection(self):
        """Test detection of text that needs transliteration"""
        # Should detect English Latin characters from transliteration map
        self.assertTrue(GreekTransliterationService.needs_transliteration("DHMOS"))
        self.assertTrue(GreekTransliterationService.needs_transliteration("YPOURGEIA"))
        
        # Should not detect already Greek text
        self.assertFalse(GreekTransliterationService.needs_transliteration("ΔΗΜΟΣ"))
        
        # Should not detect random characters not in map
        self.assertFalse(GreekTransliterationService.needs_transliteration("1234567"))
    
    def test_transliterate_query_smart(self):
        """Test the smart transliterate_query method"""
        # Should transliterate when needed
        result = GreekTransliterationService.transliterate_query("DHMOS")
        self.assertEqual(result, "ΔΗΜΟΣ")
        
        # Should not transliterate when not needed (already Greek)
        greek_text = "ΔΗΜΟΣ"
        result = GreekTransliterationService.transliterate_query(greek_text)
        self.assertEqual(result, greek_text)
        
        # Should handle empty string
        result = GreekTransliterationService.transliterate_query("")
        self.assertEqual(result, "")
    
    def test_transliterate_all_single_letters(self):
        """Test all supported single Latin to Greek letter mappings"""
        mapping_tests = {
            'A': 'Α',
            'B': 'Β',
            'G': 'Γ',
            'D': 'Δ',
            'E': 'Ε',
            'Z': 'Ζ',
            'H': 'Η',
            'I': 'Ι',
            'K': 'Κ',
            'L': 'Λ',
            'M': 'Μ',
            'N': 'Ν',
            'X': 'Ξ',
            'O': 'Ο',
            'P': 'Π',
            'R': 'Ρ',
            'S': 'Σ',
            'T': 'Τ',
            'U': 'Υ',
            'W': 'Ω',
        }
        
        for latin, greek in mapping_tests.items():
            result = GreekTransliterationService.transliterate(latin)
            self.assertEqual(result, greek, f"Failed: {latin} -> {greek}")
    
    def test_transliterate_complex_words(self):
        """Test transliteration of complex real-world examples (phonetic, not proper spelling)"""
        test_cases = {
            "GENETIKI GRAMMATEIA": "ΓΕΝΕΤΙΚΙ ΓΡΑΜΜΑΤΕΙΑ",  # phonetic transliteration
            "NOMARCHIA": "ΝΟΜΑΡΧΙΑ",
            "DHMOTIKI EPICHEIRISI": "ΔΗΜΟΤΙΚΙ ΕΠΙΧΕΙΡΙΣΙ",  # phonetic transliteration
            "YPARXIA NOMOU": "ΥΠΑΡΞΙΑ ΝΟΜΟΥ",
        }
        
        for english, expected_greek in test_cases.items():
            result = GreekTransliterationService.transliterate(english)
            self.assertEqual(result, expected_greek, f"Failed: {english} -> {expected_greek}")
    
    def test_transliterate_preserves_word_boundaries(self):
        """Test that word boundaries and punctuation are preserved"""
        result = GreekTransliterationService.transliterate("DHMOS, ATHINAION!")
        self.assertIn(",", result)
        self.assertIn("!", result)
    
    def test_transliterate_handles_none(self):
        """Test handling of None input"""
        # Should not crash but return the input
        result = GreekTransliterationService.transliterate(None)
        self.assertEqual(result, None)


class TestTransliterationIntegration(TestCase):
    """Integration tests for transliteration in search context"""
    
    def test_search_query_transliteration_flow(self):
        """Test the complete flow of transliterating a search query"""
        # Simulate what happens in search_stream_api
        user_input = "DHMOS"
        
        # Step 1: Transliterate
        transliterated = GreekTransliterationService.transliterate_query(user_input)
        
        # Step 2: Verify it was transliterated
        self.assertEqual(transliterated, "ΔΗΜΟΣ")
    
    def test_mixed_greek_latin_query(self):
        """Test query with both Greek and Latin characters"""
        # User types mixed
        query = "DHMOS ATHENON"
        
        transliterated = GreekTransliterationService.transliterate_query(query)
        
        # First word should be transliterated
        self.assertIn("ΔΗΜΟΣ", transliterated)
        # Should handle both languages
        self.assertIn("Α", transliterated)  # Greek A


# Performance test
@pytest.mark.benchmark
class TestTransliterationPerformance(TestCase):
    """Performance tests for transliteration"""
    
    def test_transliteration_speed(self):
        """Test that transliteration is fast enough for real-time search"""
        import time
        
        test_queries = [
            "DHMOS",
            "YPOURGEIA",
            "PERIFEREIA",
            "GENETIKI GRAMMATEIA",
            "NOMARCHIA",
            "DHMOTIKI EPICHEIRISI",
        ]
        
        start = time.time()
        for _ in range(1000):
            for query in test_queries:
                GreekTransliterationService.transliterate_query(query)
        end = time.time()
        
        # Should be very fast (translating 6000 queries should take < 1 second)
        elapsed = end - start
        self.assertLess(elapsed, 1.0, 
                       f"Transliteration too slow: {elapsed:.2f}s for 6000 queries")
