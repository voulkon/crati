import pytest
import os
from django.test import override_settings
from core.tasks.tasks_decisions_import import store_decisions_from_pickle
from core.models.decisions import Decision as DecisionModel


# Force SQLite for this test to avoid connection issues
@pytest.mark.django_db
@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
)
def test_store_decisions_from_pickle(a_pickle_to_store):
    initial_count = DecisionModel.objects.count()

    # Call the task function directly (not through Celery)
    result = store_decisions_from_pickle.run(str(a_pickle_to_store))

    final_count = DecisionModel.objects.count()

    # Check that decisions were actually created
    assert final_count > initial_count, f"No new decisions were stored from the pickle file. Initial: {initial_count}, Final: {final_count}"

    # Check that the task result indicates success AND actual creation
    assert result['status'] == 'success'
    assert result['decisions_created'] > 0, f"Task reported creating {result['decisions_created']} decisions, but should have created some"

    print(f"Test passed: {result['decisions_created']} decisions created")