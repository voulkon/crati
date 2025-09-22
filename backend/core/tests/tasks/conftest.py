import pytest
from pathlib import Path
from loguru import logger

@pytest.fixture
def tasks_modules_data_path(data_for_testing_path)->Path:
    return data_for_testing_path / "for_tasks"

@pytest.fixture
def a_pickle_to_store(tasks_modules_data_path) -> Path:
    pkl_path = tasks_modules_data_path / "chunk_2025-09-19_1_225009.pkl"
    parent_dir = pkl_path.parent
    
    return pkl_path

