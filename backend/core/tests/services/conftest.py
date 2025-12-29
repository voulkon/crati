from pathlib import Path
import pytest
import vcr
from core.importers.decisions import DecisionImporter
from core.models.decisions import Decision as DecisionModel
from core.services.decision_ingestion_service import DecisionIngestionService
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher

@pytest.fixture
def corrupted_file_name() -> str:
    """Fixture to provide the name of a corrupted file."""
    return "Corrupted_text - 9ΑΦΞ6-ΧΚΗ.pdf"

@pytest.fixture
def not_corrupted_file_name() -> str:
    """Fixture to provide the name of a not corrupted file."""
    return "Not_Corrupted - ΨΑ8Α469Β7Ι-ΤΔΒ.pdf"

@pytest.fixture
def corrupted_file_path(pdf_for_testing_path, corrupted_file_name) -> Path:
    """Fixture to provide the path of a corrupted file."""
    the_path = pdf_for_testing_path / Path(corrupted_file_name)
    # Ensure the file exists in the test directory
    if not the_path.exists():
        raise FileNotFoundError(f"Test file {the_path} does not exist. Please ensure it is present in the test directory.")
    return the_path

@pytest.fixture
def not_corrupted_file_path(pdf_for_testing_path, not_corrupted_file_name) -> Path:
    """Fixture to provide the path of a not corrupted file."""
    the_path = pdf_for_testing_path / Path(not_corrupted_file_name)
    # Ensure the file exists in the test directory
    if not the_path.exists():
        raise FileNotFoundError(f"Test file {the_path} does not exist. Please ensure it is present in the test directory.")
    return the_path


# --- VCR Integration Tests ---

@pytest.fixture
def vcr_config():
    """Provide VCR configuration for tests."""
    return vcr.VCR(
        serializer='yaml',
        cassette_library_dir='fixtures/vcr_cassettes',
        record_mode='once',
        match_on=['uri', 'method'],
        decode_compressed_response=True,
    )


@pytest.fixture
def daily_decisions_vcr_cassette(vcr_config):
    """Factory fixture to create VCR cassettes."""
    def _create_cassette(cassette_name):
        return vcr_config.use_cassette(cassette_name)
    return _create_cassette

# --- Helper Fixtures ---

@pytest.fixture
def a_test_diavgeia_fetcher() -> DiavgeiaFetcher:
    """Provides a MagicMock for the DiavgeiaFetcher."""
    return DiavgeiaFetcher()


@pytest.fixture
def a_test_decision_service(mock_diavgeia_fetcher: DiavgeiaFetcher) -> DecisionIngestionService:
    """Provides an instance of the service with a mocked fetcher and zero delay."""
    # Use delay=0 for tests to avoid actual sleeping
    return DecisionIngestionService(mock_diavgeia_fetcher, delay_seconds=20)
