# Basic comparison
python manage.py compare_extractors_direct --ada YOUR_ADA_HERE

# No chunks mode (Docling won't split)
python manage.py compare_extractors_direct --ada YOUR_ADA_HERE --no-chunks

# Save results to file for detailed inspection
python manage.py compare_extractors_direct --ada YOUR_ADA_HERE --output-file ./comparison_results.json