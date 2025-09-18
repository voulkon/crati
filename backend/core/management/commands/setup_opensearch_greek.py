import requests
import json
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Setup OpenSearch with Greek language support and stemming"

    def handle(self, *args, **options):
        opensearch_url = getattr(settings, 'OPENSEARCH_URL', 'http://opensearch:9200')
        
        self.stdout.write(self.style.SUCCESS("=== Setting up OpenSearch for Greek Documents ==="))
        
        # 1. Create index template for Greek documents
        self.create_greek_index_template(opensearch_url)
        
        # 2. Create the main Greek documents index
        self.create_greek_documents_index(opensearch_url)
        
        # 3. Test the setup
        self.test_greek_analysis(opensearch_url)
        
        self.stdout.write(self.style.SUCCESS("=== OpenSearch Greek setup completed ==="))

    def create_greek_index_template(self, opensearch_url):
        self.stdout.write("\n--- Creating Greek Index Template ---")
        
        # Simplified template config to avoid errors
        template_config = {
            "index_patterns": ["greek-*", "diavgeia-*"],
            "template": {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "analysis": {
                        "analyzer": {
                            "greek_text_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "icu_folding",
                                    "lowercase", 
                                    "greek_stemmer"
                                ]
                            }
                        },
                        "filter": {
                            "greek_stemmer": {
                                "type": "stemmer",
                                "language": "greek"
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "decision_id": {"type": "integer"},
                        "ada": {"type": "keyword"},
                        "title": {
                            "type": "text",
                            "analyzer": "greek_text_analyzer"
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "greek_text_analyzer"
                        }
                    }
                }
            }
        }
        
        try:
            response = requests.put(
                f"{opensearch_url}/_index_template/greek-documents-template",
                json=template_config,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code in [200, 201]:
                self.stdout.write(self.style.SUCCESS("✓ Greek index template created"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Template creation failed: {response.status_code}"))
                self.stdout.write(f"Response: {response.text}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Template creation error: {e}"))

    def create_greek_documents_index(self, opensearch_url):
        self.stdout.write("\n--- Creating Main Greek Documents Index ---")
        
        try:
            # Delete if exists
            requests.delete(f"{opensearch_url}/diavgeia-documents")
            
            response = requests.put(f"{opensearch_url}/diavgeia-documents")
            
            if response.status_code in [200, 201]:
                self.stdout.write(self.style.SUCCESS("✓ Main documents index created"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Index creation failed: {response.status_code}"))
                self.stdout.write(f"Response: {response.text}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Index creation error: {e}"))

    def test_greek_analysis(self, opensearch_url):
        self.stdout.write("\n--- Testing Greek Analysis Setup ---")
        
        test_cases = ["κριτήρια", "αποφάσεις", "ΠΟΣΟΤΗΤΑ"]
        
        for text in test_cases:
            try:
                analyze_request = {
                    "analyzer": "greek_text_analyzer",
                    "text": text
                }
                
                response = requests.post(
                    f"{opensearch_url}/diavgeia-documents/_analyze",
                    json=analyze_request
                )
                
                if response.status_code == 200:
                    result = response.json()
                    tokens = [token['token'] for token in result.get('tokens', [])]
                    self.stdout.write(f"  '{text}' → {tokens}")
                else:
                    self.stdout.write(f"  Analysis failed for '{text}': {response.status_code}")
                    self.stdout.write(f"  Response: {response.text}")
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Test error: {e}"))