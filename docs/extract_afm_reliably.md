## From inside the container:

python manage.py generate_afm_test_data \
    --output-dir "core/tests/data/afm_test_patterns" \
    --max-examples-per-pattern 5 \
    --include-edge-cases
