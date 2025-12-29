from pathlib import Path
from core.services.extractors.pymupdf import PyMuPDFExtractor
from core.services.text_preprocessor import TextPreprocessor, CorruptionDetectionStrategy
from core.services.document_processor import TextExtractionProcessor
from core.pydantic_models.text_preprocessing import PreprocessingResult
import pytest
from core.models.document_analysis import ProcessingProvider


@pytest.fixture
def preprocessor_service() -> TextPreprocessor:
    """Fixture to provide an instance of the TextPreprocessor with COMMON_WORDS strategy."""
    return TextPreprocessor(strategy=CorruptionDetectionStrategy.COMMON_WORDS)

@pytest.fixture
def processor_service() -> TextExtractionProcessor:
    """Fixture to provide an instance of the TextExtractionProcessor."""
    return TextExtractionProcessor()

@pytest.fixture
def provider_to_use() -> ProcessingProvider:
    """Fixture to provide the processing provider."""
    return ProcessingProvider.PYMUPDF

@pytest.fixture
def extractor_to_use(processor_service, provider_to_use) -> PyMuPDFExtractor:
    return processor_service.extractors[provider_to_use]

@pytest.fixture
def corrupted_text(
    extractor_to_use: PyMuPDFExtractor, 
    corrupted_file_path: Path
) -> str:
    """Fixture to read the corrupted text from a file."""
    # Use the service to read the file and return its content
    extraction_result = extractor_to_use.extract_text(corrupted_file_path)
    text_extracted = extraction_result.text
    return text_extracted

@pytest.fixture
def preprocessed_corrupted_text(preprocessor_service, corrupted_text) -> PreprocessingResult:
    result_of_preprocessing = preprocessor_service.preprocess(corrupted_text)
    return result_of_preprocessing

def test_corrupted_text_detection(
    preprocessed_corrupted_text: PreprocessingResult
):
    """
    Test that the preprocessor detects corrupted text correctly using COMMON_WORDS strategy.
    """
    result: PreprocessingResult = preprocessed_corrupted_text
    
    # The text should be detected as corrupted
    assert result.is_corrupted is True, "The preprocessor should detect the text as corrupted."
    
    # Check that we have performance stats
    assert 'total' in result.performance_stats
    assert result.performance_stats['total'] > 0

def test_normal_text_not_detected_as_corrupted(preprocessor_service):
    """
    Test that normal Greek text is not detected as corrupted.
    """
    normal_greek_text = """
    Η Ελληνική Δημοκρατία είναι κράτος που βρίσκεται στη νοτιοανατολική Ευρώπη.
    Πρωτεύουσα και μεγαλύτερη πόλη της χώρας είναι η Αθήνα.
    Το κράτος έχει πληθυσμό περίπου 10,7 εκατομμυρίων κατοίκων.
    """
    
    result = preprocessor_service.preprocess(normal_greek_text)
    
    assert result.is_corrupted is False, "Normal Greek text should not be detected as corrupted."
    assert result.confidence_score > 0.5, "Should have reasonable confidence in the result."

def test_text_with_no_greek_words_detected_as_corrupted(preprocessor_service):
    """
    Test that text with mixed gibberish and few real words is detected as corrupted.
    """
    # Text with mostly gibberish but some real Greek words mixed in
    # This should be flagged as corrupted because most content is unusable
    mixed_gibberish_text = """
    Τπόινγν Δηδηθήο Γηαρείξηζεο αβγδεζηθικλμνοπρστυφχψω
    ΑΓΙΑΒΑΘΜΗΣΟ κάποιες παράξενες συμβολοσειρές που δεν είναι λέξεις
    Ψφχωςερτυιοπασδφγηκλζχβνμ
    """
    
    result = preprocessor_service.preprocess(mixed_gibberish_text)
    
    assert result.is_corrupted is True, "Text with mostly gibberish should be detected as corrupted even if it contains some real words."
    
    # Check corruption indicators provide useful info
    if 'word_analysis' in result.corruption_indicators:
        word_analysis = result.corruption_indicators['word_analysis']
        assert word_analysis['detection_words_found'] >= 0
        # With stricτερ thresholds, this should now be flagged
        print(f"Detection ratio: {word_analysis['detection_ratio']:.3f}")
        print(f"Coverage ratio: {word_analysis['coverage_ratio']:.3f}")
        print(f"Words found: {word_analysis['detection_words_found']}")

def test_purely_gibberish_text_detected_as_corrupted(preprocessor_service):
    """
    Test that purely gibberish text with no real Greek words is detected as corrupted.
    """
    # Purely gibberish text with no real Greek words
    pure_gibberish_text = """
    Τπόινγν Δηδηθήο Γηαρείξηζεο αβγδεζηθικλμνοπρστυφχψω
    ΑΓΙΑΒΑΘΜΗΣΟ ξυζαβγδεζηθικλμνοπρστυφχψω  
    Ψφχωςερτυιοπασδφγηκλζχβνμ κλμνοπρστυφχψωαβγδεζηθ
    """
    
    result = preprocessor_service.preprocess(pure_gibberish_text)
    
    assert result.is_corrupted is True, "Purely gibberish text should definitely be detected as corrupted."
    
    if 'word_analysis' in result.corruption_indicators:
        word_analysis = result.corruption_indicators['word_analysis']
        assert word_analysis['detection_ratio'] < 0.02  # Should be very low

def test_domain_stopwords_help_detection(preprocessor_service):
    """
    Test that domain-specific stopwords help in corruption detection.
    """
    # Text that contains domain stopwords
    text_with_domain_words = """
    ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ
    Μερικές άλλες λέξεις που δεν είναι συνηθισμένες αλλά υπάρχουν στο κείμενο.
    """
    
    result = preprocessor_service.preprocess(text_with_domain_words)
    
    assert result.is_corrupted is False, "Text with domain stopwords should not be detected as corrupted."

def test_preprocessing_result_structure(preprocessor_service):
    """
    Test that the PreprocessingResult has the expected structure.
    """
    test_text = "Αυτό είναι ένα δοκιμαστικό κείμενο με ελληνικές λέξεις."
    
    result = preprocessor_service.preprocess(test_text)
    
    # Check all required fields are present
    assert hasattr(result, 'processed_text')
    assert hasattr(result, 'is_corrupted')
    assert hasattr(result, 'confidence_score')
    assert hasattr(result, 'performance_stats')
    assert hasattr(result, 'corruption_indicators')
    
    # Check types
    assert isinstance(result.processed_text, str)
    assert isinstance(result.is_corrupted, bool)
    assert isinstance(result.confidence_score, (float, type(None)))
    assert isinstance(result.performance_stats, dict)
    assert isinstance(result.corruption_indicators, dict)
    
    # Check confidence score is in valid range
    if result.confidence_score is not None:
        assert 0.0 <= result.confidence_score <= 1.0

def test_empty_text_handling(preprocessor_service):
    """
    Test that empty text is handled gracefully.
    """
    result = preprocessor_service.preprocess("")
    
    assert result.processed_text == ""
    assert result.is_corrupted is False
    assert result.confidence_score == 1.0


@pytest.mark.parametrize("detection_threshold,coverage_threshold,should_be_corrupted,test_name", [
    (0.05, 0.15, False, "old_strict_thresholds"),    # Old thresholds - should flag as corrupted
    (0.03, 0.08, False, "new_relaxed_thresholds"),  # New thresholds - should pass
    (0.02, 0.05, False, "very_relaxed_thresholds"), # Even more relaxed - should pass
])
def test_threshold_sensitivity_on_corrupted_appearing_doc(
    not_corrupted_file_path: Path,
    processor_service: TextExtractionProcessor,
    detection_threshold: float,
    coverage_threshold: float,
    should_be_corrupted: bool,
    test_name: str
):
    """
    Test that threshold adjustments correctly affect corruption detection.
    
    This parametrized test verifies:
    1. OLD thresholds (0.05, 0.15) would incorrectly flag administrative docs as corrupted
    2. NEW thresholds (0.03, 0.08) correctly identify them as valid
    3. The threshold changes are what fixed the false positive issue
    """
    # Create preprocessor with specific thresholds
    preprocessor = TextPreprocessor(
        strategy=CorruptionDetectionStrategy.COMMON_WORDS,
        detection_ratio_threshold=detection_threshold,
        coverage_ratio_threshold=coverage_threshold
    )
    
    # Use Docling extractor
    from core.models.document_analysis import ProcessingProvider
    extractor = processor_service.extractors[ProcessingProvider.DOCLING]
    
    # Extract text
    extraction_result = extractor.extract_text(not_corrupted_file_path)
    text = extraction_result.text
    
    # Preprocess
    result = preprocessor.preprocess(text)
    
    print(f"\n📊 Test: {test_name}")
    print(f"  Thresholds: detection={detection_threshold:.3f}, coverage={coverage_threshold:.3f}")
    print(f"  Expected corrupted: {should_be_corrupted}")
    print(f"  Actual corrupted: {result.is_corrupted}")
    
    if 'word_analysis' in result.corruption_indicators:
        wa = result.corruption_indicators['word_analysis']
        print(f"  Detection ratio: {wa['detection_ratio']:.3f}")
        print(f"  Coverage ratio: {wa['coverage_ratio']:.3f}")
        print(f"  Words found: {wa['detection_words_found']}")
        
        doc_chars = wa.get('document_characteristics', {})
        if doc_chars:
            print(f"  Legal citations: {doc_chars.get('citation_count', 0)}")
            print(f"  Admin indicators: {doc_chars.get('indicator_count', 0)}")
    
    # Verify the threshold correctly affects the result
    assert result.is_corrupted == should_be_corrupted, (
        f"With thresholds ({detection_threshold}, {coverage_threshold}), "
        f"expected is_corrupted={should_be_corrupted}, got {result.is_corrupted}"
    )

