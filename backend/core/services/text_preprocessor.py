import re
import json
import time
import html
from typing import Tuple, Set, List, Optional, Dict, Any
from pathlib import Path
from loguru import logger
from enum import Enum
from core.pydantic_models.text_preprocessing import (
    PreprocessingResult, CorruptionDetectionStrategy
    )

class TextPreprocessor:
    def __init__(self, 
                 strategy: CorruptionDetectionStrategy = CorruptionDetectionStrategy.COMMON_WORDS,
                 dictionary_path: Optional[Path] = None,
                 char_validity_threshold: float = 0.7,
                 detection_ratio_threshold: float = 0.05,
                 coverage_ratio_threshold: float = 0.15
                 ):
        
        self.char_validity_threshold = char_validity_threshold
        self.detection_ratio_threshold = detection_ratio_threshold
        self.coverage_ratio_threshold = coverage_ratio_threshold
        
        # Load Greek stopwords - domain-specific terms from Greek government decisions
        self.greek_stopwords: Set[str] = {
            "ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ",
            "ΥΠΟΥΡΓΕΙΟ", 
            "ΔΙΟΙΚΗΣΗ",
            "ΑΠΟΦΑΣΗ",
            "ΝΟΜΟΣ",
            "ΑΡΘΡΟ",
            "ΠΑΡΑΓΡΑΦΟΣ",
            "ΚΥΒΕΡΝΗΣΗ",
            "ΠΡΩΘΥΠΟΥΡΓΟΣ",
            "ΥΠΟΥΡΓΟΣ",
            "ΓΕΝΙΚΟΣ ΓΡΑΜΜΑΤΕΑΣ",
            "ΔΙΕΥΘΥΝΤΗΣ",
            "ΔΗΜΟΣΙΑ ΔΙΟΙΚΗΣΗ",
            "ΔΗΜΟΣΙΟΣ ΤΟΜΕΑΣ",
            "ΟΡΓΑΝΙΣΜΟΣ",
            "ΥΠΗΡΕΣΙΑ",
            "ΦΟΡΕΑΣ"
        }
        
        # Pattern to identify Greek characters, numbers, basic punctuation, and whitespace
        # Includes: Greek letters, diacritics (΄ͺ), Latin letters (for acronyms/codes), 
        # common punctuation, markdown symbols (#), and HTML/formatting chars (<>)
        self.valid_greek_char_pattern = re.compile(
            r'^[Α-ΩΆΈΉΊΌΎΏΪΫα-ωάέήίόύώϊϋΐΰ'
            r'a-zA-Z'  # Latin letters for acronyms, codes
            r'\s\d'    # Whitespace and digits
            r'\.,;:?!€()%/\"\'\«\»\-'  # Punctuation
            r'#<>@&*+=_~`\[\]\{\}\|\\΄ͺ'  # Additional symbols, tonos, dialytika
            r']+$'
        )
        
        # Most common Greek words (lowercase only for efficiency)
        self.common_greek_words = {
            'και', 'που', 'για', 'στο', 'στη', 'στην', 'των', 'του', 'της', 'με',
            'από', 'αυτό', 'αυτή', 'αυτός', 'είναι', 'δεν', 'θα', 'να', 'ο', 'η', 
            'το', 'τα', 'οι', 'τις', 'τους', 'κατά', 'προς', 'μετά', 'πριν',
            'ενώ', 'όταν', 'εάν', 'αν', 'ή', 'αλλά', 'όμως', 'ώστε', 'διότι',
            'επειδή', 'μόνο', 'πάντα', 'ακόμη', 'ακόμα', 'όλα', 'όλες', 'όλους',
            'πολύ', 'πολλά', 'πολλές', 'πολλοί', 'μια', 'ένα', 'ένας', 'μία',
            'έχει', 'έχουν', 'έχω', 'έχεις', 'είχε', 'είχαν', 'ήταν', 'ήσαν',
            'πως', 'ότι', 'τι', 'ποιος', 'ποια', 'ποιο', 'πού', 'πότε', 'γιατί'
        }

        # Initialize strategy-specific components
        self.strategy = strategy
        self.greek_dictionary: Optional[Set[str]] = None
        self.gr_nlp_pipeline = None
        self.performance_stats: Dict[str, float] = {}
        
        self._initialize_strategy(dictionary_path)

    def _initialize_strategy(self, dictionary_path: Optional[Path]):
        """Initialize the selected corruption detection strategy."""
        try:
            if self.strategy in [CorruptionDetectionStrategy.GREEK_DICTIONARY, CorruptionDetectionStrategy.HYBRID]:
                self.greek_dictionary = self._load_greek_dictionary(dictionary_path)
            
            if self.strategy in [CorruptionDetectionStrategy.GR_NLP_TOOLKIT, CorruptionDetectionStrategy.HYBRID]:
                self._initialize_gr_nlp_toolkit()
                
        except Exception as e:
            logger.warning(f"Failed to initialize strategy {self.strategy}: {e}")
            logger.info("Falling back to common words strategy")
            self.strategy = CorruptionDetectionStrategy.COMMON_WORDS

    def _load_greek_dictionary(self, dictionary_path: Optional[Path]) -> Set[str]:
        """Load Greek dictionary from JSON file."""
        if dictionary_path and dictionary_path.exists():
            path_to_use = dictionary_path
        else:
            path_to_use = Path("data/greek_dictionary.json")
        
        if path_to_use.exists():
            try:
                with open(path_to_use, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    words = set()
                    if isinstance(data, list):
                        words.update(word.lower() for word in data)
                        words.update(word.upper() for word in data)
                    elif isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, list):
                                words.update(word.lower() for word in value)
                                words.update(word.upper() for word in value)
                    logger.info(f"Loaded {len(words)} Greek words from dictionary.")
                    return words
            except Exception as e:
                logger.warning(f"Could not load Greek dictionary: {e}")
        
        logger.info("No dictionary found, using common words as fallback.")
        return self.common_greek_words

    def _initialize_gr_nlp_toolkit(self):
        """Initialize the gr-nlp-toolkit if available."""
        try:
            import gr_nlp_toolkit
        except ImportError:
            logger.warning("gr-nlp-toolkit not available. Install with: pip install gr-nlp-toolkit")
            self.gr_nlp_pipeline = None
            return
        try:
            # Use only POS tagging as it's lighter than full pipeline
            self.gr_nlp_pipeline = gr_nlp_toolkit.Pipeline("pos", use_cpu=True)
            logger.info("Initialized gr-nlp-toolkit successfully")
        except ImportError:
            logger.warning("gr-nlp-toolkit not available. Install with: pip install gr-nlp-toolkit")
            self.gr_nlp_pipeline = None
        except Exception as e:
            logger.warning(f"Failed to initialize gr-nlp-toolkit: {e}")
            self.gr_nlp_pipeline = None

    def _extract_words(self, text: str) -> List[str]:
        """Extract words from text, filtering out numbers and very short tokens."""
        words = re.findall(r'[Α-ΩΆΈΉΊΌΎΏΪΫα-ωάέήίόύώϊϋΐΰ]+', text)
        return [word for word in words if len(word) >= 2]

    def _check_common_words_presence(self, text: str) -> Tuple[bool, float]:
        """Strategy 1: Check if sufficient common Greek words appear as whole words in the text."""
        start_time = time.time()
        
        # Convert text to lowercase for case-insensitive matching
        text_lower = text.lower()
        
        # Use combined detection words (common + domain-specific)
        detection_words = self._get_all_detection_words()
        
        # Extract actual words from text for comparison
        text_words = self._extract_words(text_lower)
        text_words_set = set(text_words)
        
        # Count how many of our detection words are found as whole words
        found_count = 0
        total_detection_words = len(detection_words)
        
        for word in detection_words:
            if word in text_words_set:
                # logger.debug(f"Detection word '{word}' found as whole word in text")
                found_count += 1
        
        # Calculate ratio of detection words found
        detection_ratio = found_count / total_detection_words if total_detection_words > 0 else 0
        
        # Also calculate ratio relative to total words in text (for additional validation)
        text_word_count = len(text_words)
        if text_word_count > 0:
            word_coverage_ratio = found_count / text_word_count
        else:
            word_coverage_ratio = 0
        
        # Corruption detection based purely on configurable thresholds:
        # 1. Low detection ratio - too few of our known words found
        # 2. Low coverage ratio - found words don't cover enough of the text
        # Both thresholds must fail for corruption (AND logic)
        
        low_detection = detection_ratio < self.detection_ratio_threshold
        low_coverage = word_coverage_ratio < self.coverage_ratio_threshold
        
        # Text is corrupted only if BOTH thresholds fail
        is_corrupted = low_detection and low_coverage
        
        processing_time = time.time() - start_time
        
        # Store detailed stats for debugging
        self.performance_stats['word_detection'] = {
            'detection_words_found': found_count,
            'total_detection_words': total_detection_words,
            'detection_ratio': detection_ratio,
            'text_word_count': text_word_count,
            'word_coverage_ratio': word_coverage_ratio,
            'corruption_reasons': {
                'low_detection': low_detection,
                'low_coverage': low_coverage
            }
        }
        
        if is_corrupted:
            logger.warning(
                f"Corruption detected: low detection ratio ({detection_ratio:.3f} < {self.detection_ratio_threshold}) "
                f"AND low coverage ({word_coverage_ratio:.3f} < {self.coverage_ratio_threshold})"
            )
        else:
            logger.debug(f"Word detection passed. Found {found_count} detection words out of {total_detection_words} "
                        f"(detection ratio: {detection_ratio:.3f}, coverage: {word_coverage_ratio:.3f})")
        
        return is_corrupted, processing_time

    def _get_all_detection_words(self) -> Set[str]:
        """Get combined set of common words and domain stopwords for detection."""
        # Combine common words with domain-specific stopwords (converted to lowercase)
        detection_words = self.common_greek_words.copy()
        
        # Add domain stopwords (converted to lowercase for consistency)
        for stopword in self.greek_stopwords:
            # Split multi-word stopwords and add individual words
            words_in_stopword = stopword.lower().split()
            detection_words.update(words_in_stopword)
        
        return detection_words

    def _check_dictionary_ratio(self, words: List[str]) -> Tuple[bool, float]:
        """Strategy 2: Check ratio of words found in Greek dictionary."""
        start_time = time.time()
        
        if not self.greek_dictionary or len(words) < 10:
            return False, time.time() - start_time
            
        # Sample words for performance (check first 50 words)
        sample_words = words[:50]
        
        # Check both lowercase and uppercase variants
        found_words = 0
        for word in sample_words:
            if word.lower() in self.greek_dictionary or word.upper() in self.greek_dictionary:
                found_words += 1
        
        # Calculate ratio of dictionary words
        dictionary_ratio = found_words / len(sample_words)
        processing_time = time.time() - start_time
        
        # If less than 20% of words are in dictionary, likely corrupted
        is_corrupted = dictionary_ratio < 0.2
        if is_corrupted:
            logger.warning(f"Corruption heuristic: Low dictionary ratio ({dictionary_ratio:.2f}).")
            
        return is_corrupted, processing_time

    def _check_gr_nlp_toolkit(self, text: str) -> Tuple[bool, float]:
        """Strategy 3: Use gr-nlp-toolkit for advanced analysis."""
        start_time = time.time()
        
        if not self.gr_nlp_pipeline:
            return False, time.time() - start_time
        
        try:
            # Take a sample of text to avoid heavy processing
            sample_text = text[:500]  # First 500 characters
            doc = self.gr_nlp_pipeline(sample_text)
            
            # Count tokens that got valid POS tags vs invalid/unknown
            valid_tokens = 0
            total_tokens = len(doc.tokens)
            
            if total_tokens == 0:
                return True, time.time() - start_time
            
            for token in doc.tokens:
                # If the toolkit can assign a valid POS tag, it's likely a real word
                if hasattr(token, 'upos') and token.upos and token.upos != 'X':  # 'X' is usually for unknown/foreign
                    valid_tokens += 1
            
            # If less than 30% of tokens get valid POS tags, likely corrupted
            valid_ratio = valid_tokens / total_tokens
            is_corrupted = valid_ratio < 0.3
            
            processing_time = time.time() - start_time
            
            if is_corrupted:
                logger.warning(f"Corruption heuristic: Low valid POS ratio ({valid_ratio:.2f}) from gr-nlp-toolkit.")
            
            return is_corrupted, processing_time
            
        except Exception as e:
            logger.warning(f"Error in gr-nlp-toolkit analysis: {e}")
            return False, time.time() - start_time

    def _check_word_length_distribution(self, words: List[str]) -> bool:
        """Check for unusual word length patterns that suggest corruption."""
        if len(words) < 20:
            return False
            
        word_lengths = [len(word) for word in words]
        
        # Check for excessive very long words
        very_long_words = sum(1 for length in word_lengths if length > 15)
        if very_long_words / len(words) > 0.15:
            logger.warning("Corruption heuristic: Too many very long words.")
            return True
            
        # Check average length - Greek words typically average 6-8 characters
        avg_length = sum(word_lengths) / len(words)
        if avg_length > 12:
            logger.warning(f"Corruption heuristic: Unusual average word length: {avg_length:.1f}")
            return True
                
        return False

    def _check_character_validity(self, text: str) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Check for high percentage of non-Greek/non-standard characters.
        Returns:
            Tuple[bool, float, Dict]: (is_corrupted, ratio_invalid, debug_info)
        """
        lines = text.splitlines()
        sample_lines = lines[:10] + lines[-10:] if len(lines) > 20 else lines
        
        non_valid_chars = 0
        total_chars_sampled = 0
        invalid_chars_found = {}  # Track which invalid chars we find
        sample_invalid_positions = []  # Track some examples with context
        
        for line_idx, line in enumerate(sample_lines):
            clean_line = line.strip()
            if not clean_line:
                continue
                
            for char_idx, char in enumerate(clean_line):
                total_chars_sampled += 1
                if not self.valid_greek_char_pattern.match(char):
                    non_valid_chars += 1
                    
                    # Track this invalid character
                    if char in invalid_chars_found:
                        invalid_chars_found[char] += 1
                    else:
                        invalid_chars_found[char] = 1
                    
                    # Store some examples with context (first 10)
                    if len(sample_invalid_positions) < 10:
                        start_pos = max(0, char_idx - 5)
                        end_pos = min(len(clean_line), char_idx + 6)
                        context = clean_line[start_pos:end_pos]
                        sample_invalid_positions.append({
                            'char': char,
                            'char_code': ord(char),
                            'hex_code': hex(ord(char)),
                            'line_idx': line_idx,
                            'char_idx': char_idx,
                            'context': context,
                            'context_highlight': context[:char_idx-start_pos] + f"[{char}]" + context[char_idx-start_pos+1:]
                        })
        
        ratio_non_valid = non_valid_chars / total_chars_sampled if total_chars_sampled > 0 else 0
        is_corrupted = ratio_non_valid > 0.7
        
        debug_info = {
            'total_chars_sampled': total_chars_sampled,
            'non_valid_chars': non_valid_chars,
            'ratio_non_valid': ratio_non_valid,
            'invalid_chars_found': invalid_chars_found,
            'sample_invalid_positions': sample_invalid_positions,
            'lines_sampled': len(sample_lines),
            'total_lines': len(lines)
        }
        
        if is_corrupted:
            logger.warning(f"Corruption heuristic: High ratio of non-valid characters ({ratio_non_valid:.2f}).")
            logger.debug(f"Invalid characters found: {invalid_chars_found}")
            logger.debug(f"Sample invalid positions: {sample_invalid_positions[:3]}")  # Log first 3 examples
        
        return is_corrupted, ratio_non_valid, debug_info

    def is_text_corrupted(self, text: str, min_length_for_check: int = 100) -> bool:
        """Detects if the text is likely corrupted using the selected strategy."""
        if not text or len(text) < min_length_for_check:
            return False

        total_start_time = time.time()

        # Heuristic 1: High percentage of non-Greek/non-standard characters
        char_corrupted, char_ratio, char_debug = self._check_character_validity(text)
        
        # Store character validation info in performance stats for debugging
        self.performance_stats['character_validation'] = {
            'ratio_invalid': char_ratio,
            'debug_info': char_debug
        }
        
        if char_corrupted:
            return True

        # Apply strategy-specific heuristics
        if self.strategy == CorruptionDetectionStrategy.COMMON_WORDS:
            is_corrupted, strategy_time = self._check_common_words_presence(text)
            self.performance_stats['common_words'] = strategy_time
            
        elif self.strategy == CorruptionDetectionStrategy.GREEK_DICTIONARY:
            words = self._extract_words(text)
            is_corrupted, strategy_time = self._check_dictionary_ratio(words)
            self.performance_stats['dictionary'] = strategy_time
            
        elif self.strategy == CorruptionDetectionStrategy.GR_NLP_TOOLKIT:
            is_corrupted, strategy_time = self._check_gr_nlp_toolkit(text)
            self.performance_stats['gr_nlp_toolkit'] = strategy_time
            
        elif self.strategy == CorruptionDetectionStrategy.HYBRID:
            # Try common words first (fastest)
            common_corrupted, common_time = self._check_common_words_presence(text)
            self.performance_stats['common_words'] = common_time
            
            if common_corrupted:
                # If common words suggest corruption, verify with dictionary
                words = self._extract_words(text)
                dict_corrupted, dict_time = self._check_dictionary_ratio(words)
                self.performance_stats['dictionary'] = dict_time
                is_corrupted = dict_corrupted
            else:
                is_corrupted = False
        else:
            is_corrupted = False

        # Additional check: word length distribution
        if not is_corrupted:
            words = self._extract_words(text)
            if self._check_word_length_distribution(words):
                is_corrupted = True

        total_time = time.time() - total_start_time
        self.performance_stats['total'] = total_time
        
        return is_corrupted

    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics for the last corruption check."""
        return self.performance_stats.copy()

    def benchmark_strategies(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Benchmark all available strategies on the given text."""
        results = {}
        
        # Test Common Words strategy
        original_strategy = self.strategy
        
        try:
            self.strategy = CorruptionDetectionStrategy.COMMON_WORDS
            start_time = time.time()
            common_result = self.is_text_corrupted(text)
            common_time = time.time() - start_time
            results['common_words'] = {
                'is_corrupted': common_result,
                'time': common_time,
                'available': True
            }
        except Exception as e:
            results['common_words'] = {'available': False, 'error': str(e)}

        # Test Dictionary strategy
        if self.greek_dictionary:
            try:
                self.strategy = CorruptionDetectionStrategy.GREEK_DICTIONARY
                start_time = time.time()
                dict_result = self.is_text_corrupted(text)
                dict_time = time.time() - start_time
                results['dictionary'] = {
                    'is_corrupted': dict_result,
                    'time': dict_time,
                    'available': True
                }
            except Exception as e:
                results['dictionary'] = {'available': False, 'error': str(e)}
        else:
            results['dictionary'] = {'available': False, 'error': 'No dictionary loaded'}

        # Test GR-NLP-Toolkit strategy
        if self.gr_nlp_pipeline:
            try:
                self.strategy = CorruptionDetectionStrategy.GR_NLP_TOOLKIT
                start_time = time.time()
                nlp_result = self.is_text_corrupted(text)
                nlp_time = time.time() - start_time
                results['gr_nlp_toolkit'] = {
                    'is_corrupted': nlp_result,
                    'time': nlp_time,
                    'available': True
                }
            except Exception as e:
                results['gr_nlp_toolkit'] = {'available': False, 'error': str(e)}
        else:
            results['gr_nlp_toolkit'] = {'available': False, 'error': 'gr-nlp-toolkit not initialized'}

        # Restore original strategy
        self.strategy = original_strategy
        
        return results

    def remove_stopwords(self, text: str) -> str:
        """Removes predefined stopwords from the text."""
        processed_text = text
        for stopword in self.greek_stopwords:
            pattern = re.compile(r'\b' + re.escape(stopword) + r'\b', re.IGNORECASE | re.UNICODE)
            processed_text = pattern.sub("", processed_text)
        
        processed_text = re.sub(r'\s{2,}', ' ', processed_text).strip()
        return processed_text

    def preprocess(self, text: str) -> Tuple[str, bool]:
        """
        Applies all preprocessing steps.
        Returns:
            Tuple[str, bool]: (processed_text, is_corrupted_flag)
        """
        if not text or text.isspace():
            return PreprocessingResult(
                processed_text="",
                is_corrupted=False,
                confidence_score=1.0,
                performance_stats={},
                corruption_indicators={}
            )
        
        self.performance_stats = {}

        # 0. Decode HTML entities (e.g., &lt; → <, &amp; → &)
        text = html.unescape(text)

        # 1. Detect corruption on the original raw text
        is_corrupted = self.is_text_corrupted(text)

        # 2. Calculate confidence score based on multiple factors  
        confidence_score = self._calculate_confidence_score()
        
        # 3. Perform stopword removal and other cleaning
        processed_text = self.remove_stopwords(text)
        
        # 4. Gather corruption indicators for transparency
        corruption_indicators = self._gather_corruption_indicators()

        return PreprocessingResult(
            processed_text=processed_text,
            is_corrupted=is_corrupted,
            confidence_score=confidence_score,
            performance_stats=self.performance_stats.copy(),
            corruption_indicators=corruption_indicators
        )

    def debug_character_validation(self, text: str) -> Dict[str, Any]:
        """
        Debug method to analyze character validation in detail.
        Use this to understand why text is being flagged as corrupted.
        """
        _, _, debug_info = self._check_character_validity(text)
        
        print("=== Character Validation Debug Report ===")
        print(f"Total characters sampled: {debug_info['total_chars_sampled']}")
        print(f"Invalid characters found: {debug_info['non_valid_chars']}")
        print(f"Invalid ratio: {debug_info['ratio_non_valid']:.3f}")
        print(f"Lines sampled: {debug_info['lines_sampled']} out of {debug_info['total_lines']}")
        
        if debug_info['invalid_chars_found']:
            print("\nInvalid characters breakdown:")
            for char, count in sorted(debug_info['invalid_chars_found'].items(), key=lambda x: x[1], reverse=True):
                print(f"  '{char}' (U+{ord(char):04X}): {count} times")
        
        if debug_info['sample_invalid_positions']:
            print("\nSample invalid character positions:")
            for i, pos in enumerate(debug_info['sample_invalid_positions'][:5]):  # Show first 5
                print(f"  {i+1}. Character '{pos['char']}' (U+{pos['char_code']:04X}) at line {pos['line_idx']}, position {pos['char_idx']}")
                print(f"     Context: {pos['context_highlight']}")
        
        print("\nValid character pattern:")
        print(f"  {self.valid_greek_char_pattern.pattern}")
        
        return debug_info
    
    def _calculate_confidence_score(self) -> float:
        """Calculate confidence score for corruption detection (0.0 = no confidence, 1.0 = very confident)."""
        confidence_factors = []
        
        # Factor 1: Word detection confidence
        if 'word_detection' in self.performance_stats:
            word_stats = self.performance_stats['word_detection']
            detection_ratio = word_stats.get('detection_ratio', 0)
            coverage_ratio = word_stats.get('word_coverage_ratio', 0)
            
            # Higher ratios = higher confidence in "not corrupted"
            word_confidence = min(1.0, (detection_ratio * 10) + (coverage_ratio * 2))
            confidence_factors.append(word_confidence)
        
        # Factor 2: Character validity confidence
        if 'character_validation' in self.performance_stats:
            char_stats = self.performance_stats['character_validation']
            invalid_ratio = char_stats.get('ratio_invalid', 0)
            
            # Lower invalid ratio = higher confidence in "not corrupted"
            char_confidence = max(0.0, 1.0 - (invalid_ratio * 1.5))
            confidence_factors.append(char_confidence)
        
        # Factor 3: Strategy-specific confidence
        if self.strategy == CorruptionDetectionStrategy.COMMON_WORDS and 'common_words' in self.performance_stats:
            # Fast execution suggests simple, reliable detection
            exec_time = self.performance_stats.get('common_words', 0)
            time_confidence = max(0.5, 1.0 - (exec_time * 10))  # Penalty for slow execution
            confidence_factors.append(time_confidence)
        
        # Return average confidence, or 0.5 if no factors available
        return sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.5

    def _gather_corruption_indicators(self) -> Dict[str, Any]:
        """Gather detailed information about what triggered corruption detection."""
        indicators = {}
        
        # Word-based indicators
        if 'word_detection' in self.performance_stats:
            word_stats = self.performance_stats['word_detection']
            indicators['word_analysis'] = {
                'detection_words_found': word_stats.get('detection_words_found', 0),
                'total_detection_words': word_stats.get('total_detection_words', 0),
                'detection_ratio': word_stats.get('detection_ratio', 0),
                'text_word_count': word_stats.get('text_word_count', 0),
                'coverage_ratio': word_stats.get('word_coverage_ratio', 0),
                'thresholds': {
                    'detection_ratio_threshold': self.detection_ratio_threshold,
                    'coverage_ratio_threshold': self.coverage_ratio_threshold
                }
            }
        
        # Character-based indicators
        if 'character_validation' in self.performance_stats:
            char_stats = self.performance_stats['character_validation']
            char_debug = char_stats.get('debug_info', {})
            indicators['character_analysis'] = {
                'invalid_ratio': char_debug.get('ratio_non_valid', 0),
                'invalid_char_count': char_debug.get('non_valid_chars', 0),
                'total_chars_sampled': char_debug.get('total_chars_sampled', 0),
                'threshold': char_debug.get('threshold_used', self.char_validity_threshold),
                'top_invalid_chars': dict(list(char_debug.get('invalid_chars_found', {}).items())[:5])  # Top 5 invalid chars
            }
        
        # Strategy used
        indicators['strategy_used'] = self.strategy.value
        
        return indicators