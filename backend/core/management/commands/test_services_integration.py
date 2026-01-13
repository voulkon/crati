import requests
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from django.conf import settings

class Command(BaseCommand):
    help = "Test integration with OpenSearch and Greek analysis"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Testing OpenSearch Greek Analysis Integration ==="))
        
        self.test_opensearch_health()
        self.test_icu_plugin()
        self.test_greek_analysis()
        
        self.stdout.write(self.style.SUCCESS("=== All tests completed ==="))

    def test_opensearch_health(self):
        self.stdout.write("\n--- Testing OpenSearch Health ---")
        if not settings.INDEX_THE_OPENSEARCH:
            self.stdout.write(self.style.WARNING("OpenSearch indexing is disabled in settings. Skipping tests."))
            return
        opensearch_url = getattr(settings, 'OPENSEARCH_URL', 'http://opensearch:9200')
        
        try:
            response = requests.get(f"{opensearch_url}/_cluster/health")
            health = response.json()
            self.stdout.write(f"Cluster health: {health.get('status')}")
            self.stdout.write(f"Number of nodes: {health.get('number_of_nodes')}")
            self.stdout.write(self.style.SUCCESS("✓ OpenSearch is healthy"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ OpenSearch error: {e}"))

    def test_icu_plugin(self):
        self.stdout.write("\n--- Testing ICU Plugin ---")
        
        opensearch_url = getattr(settings, 'OPENSEARCH_URL', 'http://opensearch:9200')
        if not settings.INDEX_THE_OPENSEARCH:
            self.stdout.write(self.style.WARNING("OpenSearch indexing is disabled in settings. Skipping tcu_plugin."))
        
        try:
            # Check if ICU plugin is installed
            response = requests.get(f"{opensearch_url}/_cat/plugins")
            plugins = response.text
            
            if 'analysis-icu' in plugins:
                self.stdout.write(self.style.SUCCESS("✓ ICU Analysis plugin is installed"))
            else:
                self.stdout.write(self.style.ERROR("✗ ICU Analysis plugin not found"))
                self.stdout.write(f"Installed plugins: {plugins}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Plugin check error: {e}"))

    def test_greek_analysis(self):
        self.stdout.write("\n--- Testing Greek Text Analysis ---")
        if not settings.INDEX_THE_OPENSEARCH:
            self.stdout.write(self.style.WARNING("OpenSearch indexing is disabled in settings. Skipping test_greek_analysis."))
            return
        opensearch_url = getattr(settings, 'OPENSEARCH_URL', 'http://opensearch:9200')
        
        try:
            # Create a simple test index first
            index_name = "test-greek-analysis"
            
            # Simple index config for testing
            index_config = {
                "settings": {
                    "analysis": {
                        "analyzer": {
                            "test_greek_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "icu_folding",
                                    "lowercase",
                                    "stemmer_greek"
                                ]
                            }
                        },
                        "filter": {
                            "stemmer_greek": {
                                "type": "stemmer",
                                "language": "greek"
                            }
                        }
                    }
                }
            }
            
            # Delete index if exists
            requests.delete(f"{opensearch_url}/{index_name}")
            
            # Create index
            response = requests.put(
                f"{opensearch_url}/{index_name}",
                json=index_config
            )
            
            if response.status_code in [200, 201]:
                self.stdout.write(self.style.SUCCESS(f"✓ Test index created: {response.status_code}"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Index creation failed: {response.status_code}"))
                self.stdout.write(f"Response: {response.text}")
                return
            
            # Test Greek text analysis
            test_cases = [
                "κριτήρια",  # criteria
                "αποφάσεις", # decisions
                "ΠΟΣΟΤΗΤΑ",  # quantity
                "μηχανές"    # machines
            ]
            
            for text in test_cases:
                analyze_request = {
                    "analyzer": "test_greek_analyzer",
                    "text": text
                }
                
                response = requests.post(
                    f"{opensearch_url}/{index_name}/_analyze",
                    json=analyze_request
                )
                
                if response.status_code == 200:
                    result = response.json()
                    tokens = [token['token'] for token in result.get('tokens', [])]
                    
                    self.stdout.write(f"  '{text}' → {tokens}")
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Analysis successful"))
                else:
                    self.stdout.write(self.style.ERROR(f"  ✗ Analysis failed for '{text}': {response.status_code}"))
                    self.stdout.write(f"    Response: {response.text}")
            
            # Clean up
            requests.delete(f"{opensearch_url}/{index_name}")
            self.stdout.write(self.style.SUCCESS("✓ Greek analysis working"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Analysis error: {e}"))