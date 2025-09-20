import pytest
import vcr
from core.importers.decisions import DecisionImporter
from core.models.decisions import Decision as DecisionModel
from core.services.decision_ingestion_service import DecisionIngestionService
from core.fetchers.diavgeia_fetcher import DiavgeiaFetcher

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
