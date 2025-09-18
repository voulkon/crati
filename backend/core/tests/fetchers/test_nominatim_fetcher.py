import pytest
from core.pydantic_models.geo_data import NominatimResult


@pytest.mark.impossible
def test_fetch_geo_data_success_full(
    fetched_geo_data_success_full: NominatimResult, label_to_query: str
):
    assert type(fetched_geo_data_success_full) == NominatimResult
    assert fetched_geo_data_success_full.lat is not None
    assert fetched_geo_data_success_full.lon is not None
    assert fetched_geo_data_success_full.geojson is not None
    assert fetched_geo_data_success_full.boundingbox is not None
    assert len(fetched_geo_data_success_full.boundingbox) == 4
    assert fetched_geo_data_success_full.geojson["type"] == "MultiPolygon"
