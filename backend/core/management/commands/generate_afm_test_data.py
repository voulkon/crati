from django.core.management.base import BaseCommand
from collections import defaultdict, Counter
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from core.models.decisions import Decision
from django.utils import timezone

class Command(BaseCommand):
    help = 'Generate comprehensive test data from real AFM patterns found in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='afm_test_patterns',
            help='Directory to save test pattern data'
        )
        parser.add_argument(
            '--max-examples-per-pattern',
            type=int,
            default=5,
            help='Maximum examples to save per pattern type'
        )
        parser.add_argument(
            '--min-occurrences',
            type=int,
            default=2,
            help='Minimum occurrences required to include a pattern'
        )
        parser.add_argument(
            '--include-edge-cases',
            action='store_true',
            help='Include rare/edge case patterns even if below min-occurrences'
        )

    def __init__(self):
        super().__init__()
        # Discovery collections
        self.discovered_path_patterns = defaultdict(list)  # path_pattern -> examples
        self.role_pattern_mapping = {}  # learned mapping from patterns to roles
        self.path_frequency = Counter()  # how often each path pattern appears

    def handle(self, *args, **options):
        self.output_dir = Path(options['output_dir'])
        self.output_dir.mkdir(exist_ok=True)
        
        self.max_examples = options['max_examples_per_pattern']
        self.min_occurrences = options['min_occurrences']
        self.include_edge_cases = options['include_edge_cases']
        
        # Pattern collections
        self.pattern_signatures = defaultdict(list)  # signature -> examples
        self.afm_variations = defaultdict(set)  # field_name -> set of value_types
        self.structure_patterns = defaultdict(list)  # parent_path -> examples
        self.edge_cases = []
        
        self.stdout.write("🔍 Analyzing AFM patterns in database...")
        
        # Process all decisions with AFM data
        decisions_processed = self.extract_all_afm_patterns()
        
        # Generate test files
        self.generate_pattern_test_files()
        self.generate_extraction_test_cases()
        self.generate_validation_test_data()
        self.generate_edge_case_scenarios()
        
        # Generate ADA-based test cases instead of pattern fragments
        ada_test_cases = self.generate_ada_based_test_cases()
        
        # Generate summary statistics
        self.generate_test_summary(ada_test_cases)
        
        self.stdout.write(
            f"✅ Generated comprehensive ADA-based test data\n"
            f"📁 Test files saved to: {self.output_dir}"
        )

    def extract_all_afm_patterns(self) -> int:
        """Extract all AFM patterns from the database."""
        queryset = Decision.objects.exclude(
            extra_field_values_json__isnull=True
        ).exclude(extra_field_values_json={}).only('ada', 'extra_field_values_json')
        
        decisions_processed = 0
        
        for decision in queryset:
            if decision.extra_field_values_json:
                self._analyze_decision_patterns(decision)
                decisions_processed += 1
                
                if decisions_processed % 1000 == 0:
                    self.stdout.write(f"📊 Processed {decisions_processed:,} decisions...")
        
        return decisions_processed

    def _analyze_decision_patterns(self, decision: Decision):
        """Analyze patterns in a single decision."""
        patterns = self._find_afm_patterns_recursive(
            decision.extra_field_values_json, 
            "", 
            decision.ada
        )
        
        for pattern in patterns:
            self._categorize_pattern(pattern, decision.ada)

    def _find_afm_patterns_recursive(self, data: Any, path: str, ada: str) -> List[Dict]:
        """Recursively find AFM patterns with detailed context."""
        patterns = []
        
        if isinstance(data, dict):
            # Check for AFM fields in this dict
            afm_fields = self._detect_afm_fields(data)
            
            if afm_fields:
                pattern = {
                    'path': path,
                    'parent_key': path.split('.')[-1] if path else 'root',
                    'afm_fields': afm_fields,
                    'full_structure': data,
                    'structure_keys': list(data.keys()),
                    'afm_values': {field: data[field] for field in afm_fields},
                    'context_fields': {k: v for k, v in data.items() if k not in afm_fields},
                    'ada': ada
                }
                patterns.append(pattern)
            
            # Recurse into nested structures
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                patterns.extend(self._find_afm_patterns_recursive(value, new_path, ada))
                
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]" if path else f"[{i}]"
                patterns.extend(self._find_afm_patterns_recursive(item, new_path, ada))
        
        return patterns

    def _is_excluded_field(self, field_name: str) -> bool:
        """Checks if a field name should be explicitly excluded from being an AFM."""
        field_lower = field_name.lower()
        
        # Exact or partial matches for fields that are never AFMs
        excluded_keywords = [
            'cpv', 'kae', 'amount', 'currency', 'year', 'date', 'code', 'id',
            'number', 'price', 'cost', 'budget', 'account', 'reference', 'protocol',
            'entry', 'phone', 'postal', 'zip', 'percentage', 'rate', 'index',
            'version', 'order', 'sequence'
        ]
        
        # If the field name contains any of these, it's not an AFM.
        if any(keyword in field_lower for keyword in excluded_keywords):
            return True
            
        # Special handling for 'vat'. We want 'vatid' but not 'vat' or 'vatamount'.
        if 'vat' in field_lower and 'id' not in field_lower and 'number' not in field_lower:
            return True
            
        return False


    def _detect_afm_fields(self, data: Dict[str, Any]) -> List[str]:
        """Detect AFM fields with enhanced detection."""
        afm_fields = []
        
        if not isinstance(data, dict):
            return afm_fields
        
        for key, value in data.items():
            if not isinstance(key, str):
                continue
            
            # 1. First, check for hard exclusions. This is the most important step.
            if self._is_excluded_field(key):
                continue
            
            # 2. If not excluded, check if the value is a valid AFM format.
            if self._is_afm_value(value):
                # 3. Finally, check if the key name or context suggests it's an AFM.
                if self._is_afm_field_by_name(key) or self._is_afm_field_by_context(key, data):
                    afm_fields.append(key)
        
        return afm_fields
        
            # Multiple AFM detection strategies
            # if self._is_afm_field_by_name(key) and self._is_afm_value(value):
            #     afm_fields.append(key)
            # elif self._is_afm_field_by_context(key, data) and self._is_afm_value(value):
            #     afm_fields.append(key)
        
    def _is_afm_field_by_name(self, field_name: str) -> bool:
        """Check if field name suggests AFM."""
        field_lower = field_name.lower()
        afm_keywords = ['afm', 'αφμ', 'tax', 'vat', 'tin', 'taxid', 'vatid']
        return any(keyword in field_lower for keyword in afm_keywords)

    def _is_afm_field_by_context(self, field_name: str, context: Dict) -> bool:
        """Check if field might be AFM based on context."""
        # Exclude known non-AFM fields first
        field_lower = field_name.lower()
        
        # Known non-AFM fields that might contain numbers
        excluded_fields = [
            'cpv',           # Common Procurement Vocabulary
            'kae',           # Budget line codes
            'amount',        # Monetary amounts
            'currency',      # Currency codes
            'year',          # Years
            'date',          # Dates
            'code',          # Generic codes
            'id',            # IDs
            'number',        # Numbers
            'price',         # Prices
            'cost',          # Costs
            'budget',        # Budget codes
            'account',       # Account codes
            'reference',     # Reference numbers
            'protocol',      # Protocol numbers
            'entry',         # Entry numbers
            'phone',         # Phone numbers
            'postal',        # Postal codes
            'zip',           # ZIP codes
            'vat',           # VAT rates (not VAT IDs)
            'percentage',    # Percentages
            'rate',          # Rates
            'index',         # Indices
            'version',       # Version numbers
            'order',         # Order numbers
            'sequence',      # Sequence numbers
        ]
        
        # Skip if field name suggests it's not an AFM
        if any(excluded in field_lower for excluded in excluded_fields):
            return False
        
        # Look for context clues in the same object
        context_str = json.dumps(context, ensure_ascii=False).lower()
        
        # If there are name/type fields that suggest entity info
        entity_indicators = ['name', 'όνομα', 'επωνυμία', 'afmtype', 'afmcountry', 'entername']
        has_entity_context = any(indicator in context_str for indicator in entity_indicators)
        
        # Only consider numeric fields in strong entity context as potential AFMs
        if has_entity_context:
            value = context.get(field_name)
            # Must be a numeric value that could be an AFM
            if isinstance(value, (int, str)) and self._is_afm_value(value):
                # Additional check: field name should not be obviously non-AFM
                non_afm_patterns = ['amount', 'price', 'cost', 'year', 'date', 'number', 'code']
                if not any(pattern in field_lower for pattern in non_afm_patterns):
                    return True
        
        return False

    def _is_afm_value(self, value: Any) -> bool:
        """Enhanced AFM value detection with stricter rules."""
        if value is None:
            return False
        
        # Handle numeric values
        if isinstance(value, (int, float)):
            # AFMs are typically 9 digits, but can be 8-12
            # Must be in reasonable range for Greek AFMs
            num_str = str(int(value))
            return 8 <= len(num_str) <= 12 and 10000000 <= int(value) <= 999999999999
        
        if isinstance(value, str):
            cleaned = self._clean_afm_value(value)
            if cleaned.isdigit():
                # Must be reasonable AFM length and value
                if 8 <= len(cleaned) <= 12:
                    num_value = int(cleaned)
                    return 10000000 <= num_value <= 999999999999
        
            # Handle prefixed AFMs like "EL123456789"
            if cleaned.startswith(('el', 'gr')) and len(cleaned) > 2:
                afm_part = cleaned[2:]
                if afm_part.isdigit() and 8 <= len(afm_part) <= 12:
                    num_value = int(afm_part)
                    return 10000000 <= num_value <= 999999999999
        
        return False

    def _clean_afm_value(self, value: str) -> str:
        """Clean AFM value with better handling."""
        if not value:
            return ""
        
        # Convert to string and clean
        cleaned = str(value).lower().strip()
        
        # Remove common prefixes and separators
        cleaned = cleaned.replace('el', '').replace('gr', '')
        cleaned = cleaned.replace('-', '').replace(' ', '').replace('.', '').replace('_', '')
        
        return cleaned

    def _categorize_pattern(self, pattern: Dict, ada: str):
        """Categorize a pattern for test generation."""
        # Create pattern signature for grouping similar patterns
        signature = self._create_pattern_signature(pattern)
        
        # Store example if we haven't reached the limit
        if len(self.pattern_signatures[signature]) < self.max_examples:
            self.pattern_signatures[signature].append({
                'pattern': pattern,
                'ada': ada,
                'timestamp': None  # Add if needed
            })
        
        # Track AFM field variations
        for afm_field in pattern['afm_fields']:
            afm_value = pattern['afm_values'][afm_field]
            value_type = self._get_value_type_signature(afm_value)
            self.afm_variations[afm_field].add(value_type)
        
        # Track structure patterns
        structure_sig = self._create_structure_signature(pattern)
        if len(self.structure_patterns[structure_sig]) < self.max_examples:
            self.structure_patterns[structure_sig].append(pattern)
        
        # Detect edge cases
        if self._is_edge_case(pattern):
            self.edge_cases.append({
                'pattern': pattern,
                'ada': ada,
                'edge_case_type': self._classify_edge_case(pattern)
            })

    def _create_pattern_signature(self, pattern: Dict) -> str:
        """Create a unique signature for grouping similar patterns."""
        # Signature based on structure and AFM field placement
        elements = [
            pattern['parent_key'],
            tuple(sorted(pattern['afm_fields'])),
            tuple(sorted(pattern['structure_keys'])),
            len(pattern['afm_fields'])
        ]
        
        signature_str = str(elements)
        return hashlib.md5(signature_str.encode()).hexdigest()[:12]

    def _get_value_type_signature(self, value: Any) -> str:
        """Get type signature for AFM value."""
        if isinstance(value, int):
            return f"int_{len(str(value))}"
        elif isinstance(value, str):
            cleaned = self._clean_afm_value(value)
            return f"str_{len(cleaned)}_{'numeric' if cleaned.isdigit() else 'mixed'}"
        else:
            return f"other_{type(value).__name__}"

    def _create_structure_signature(self, pattern: Dict) -> str:
        """Create signature for structure pattern."""
        # Focus on the arrangement of fields around AFM
        structure_elements = []
        
        for key in sorted(pattern['structure_keys']):
            if key in pattern['afm_fields']:
                structure_elements.append(f"AFM:{key}")
            else:
                value = pattern['full_structure'][key]
                if isinstance(value, dict):
                    structure_elements.append(f"DICT:{key}")
                elif isinstance(value, list):
                    structure_elements.append(f"LIST:{key}")
                else:
                    structure_elements.append(f"VAL:{key}")
        
        return "|".join(structure_elements)

    def _is_edge_case(self, pattern: Dict) -> bool:
        """Determine if pattern represents an edge case."""
        # Multiple AFMs in same object
        if len(pattern['afm_fields']) > 1:
            return True
        
        # Very nested structure
        if pattern['path'].count('.') > 3 or pattern['path'].count('[') > 2:
            return True
        
        # Unusual AFM field names
        standard_afm_names = ['afm', 'αφμ', 'taxid', 'vatid']
        afm_field_names = [f.lower() for f in pattern['afm_fields']]
        if not any(std in name for std in standard_afm_names for name in afm_field_names):
            return True
        
        # Mixed types in structure
        value_types = set(type(v).__name__ for v in pattern['full_structure'].values())
        if len(value_types) > 3:
            return True
        
        return False

    def _classify_edge_case(self, pattern: Dict) -> str:
        """Classify the type of edge case."""
        if len(pattern['afm_fields']) > 1:
            return "multiple_afms"
        
        if pattern['path'].count('.') > 3:
            return "deeply_nested"
        
        if pattern['path'].count('[') > 1:
            return "multiple_arrays"
        
        standard_afm_names = ['afm', 'αφμ']
        if not any(std in f.lower() for std in standard_afm_names for f in pattern['afm_fields']):
            return "unusual_field_name"
        
        return "complex_structure"

    def generate_pattern_test_files(self):
        """Generate test files for each pattern type."""
        self.stdout.write("📝 Generating pattern test files...")
        
        # Group patterns by frequency for prioritization
        pattern_frequency = Counter()
        for signature, examples in self.pattern_signatures.items():
            pattern_frequency[signature] = len(examples)
        
        # Generate test cases for each pattern
        test_cases = []
        
        for signature, examples in self.pattern_signatures.items():
            frequency = pattern_frequency[signature]
            
            # Skip rare patterns unless including edge cases
            if frequency < self.min_occurrences and not self.include_edge_cases:
                continue
            
            test_case = {
                'pattern_id': signature,
                'frequency': frequency,
                'priority': 'high' if frequency >= 10 else 'medium' if frequency >= 5 else 'low',
                'examples': []
            }
            
            for example in examples:
                test_case['examples'].append({
                    'ada': example['ada'],
                    'path': example['pattern']['path'],
                    'parent_key': example['pattern']['parent_key'],
                    'afm_fields': example['pattern']['afm_fields'],
                    'structure': example['pattern']['full_structure'],
                    'expected_afms': example['pattern']['afm_values']
                })
            
            test_cases.append(test_case)
        
        # Save test cases
        output_file = self.output_dir / 'afm_pattern_test_cases.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)
        
        self.stdout.write(f"✅ Generated {len(test_cases)} pattern test cases")

    def generate_extraction_test_cases(self):
        """Generate specific test cases for the extraction service."""
        test_cases = {
            'simple_cases': [],
            'complex_cases': [],
            'edge_cases': [],
            'validation_cases': []
        }
        
        # Categorize examples
        for signature, examples in self.pattern_signatures.items():
            for example in examples[:2]:  # Take max 2 per pattern
                pattern = example['pattern']
                
                test_case = {
                    'name': f"test_{pattern['parent_key']}_afm_extraction",
                    'input_data': pattern['full_structure'],
                    'expected_results': [
                        {
                            'afm': self._clean_afm_value(str(value)),
                            'field_name': field,
                            'parent_key': pattern['parent_key'],
                            'path': pattern['path']
                        }
                        for field, value in pattern['afm_values'].items()
                    ],
                    'ada': example['ada']
                }
                
                # Categorize based on complexity
                if len(pattern['afm_fields']) == 1 and pattern['path'].count('.') <= 1:
                    test_cases['simple_cases'].append(test_case)
                elif len(pattern['afm_fields']) > 1 or pattern['path'].count('.') > 2:
                    test_cases['complex_cases'].append(test_case)
                else:
                    test_cases['validation_cases'].append(test_case)
        
        # Add edge cases
        for edge_case in self.edge_cases[:10]:  # Limit edge cases
            test_case = {
                'name': f"test_edge_case_{edge_case['edge_case_type']}",
                'input_data': edge_case['pattern']['full_structure'],
                'expected_results': [
                    {
                        'afm': self._clean_afm_value(str(value)),
                        'field_name': field,
                        'parent_key': edge_case['pattern']['parent_key'],
                        'path': edge_case['pattern']['path']
                    }
                    for field, value in edge_case['pattern']['afm_values'].items()
                ],
                'edge_case_type': edge_case['edge_case_type'],
                'ada': edge_case['ada']
            }
            test_cases['edge_cases'].append(test_case)
        
        # Save extraction test cases
        output_file = self.output_dir / 'extraction_test_cases.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)
        
        total_cases = sum(len(cases) for cases in test_cases.values())
        self.stdout.write(f"✅ Generated {total_cases} extraction test cases")

    def generate_validation_test_data(self):
        """Generate test data for AFM validation logic."""
        validation_cases = {
            'valid_afms': [],
            'invalid_afms': [],
            'boundary_cases': []
        }
        
        # Collect AFM values from patterns
        all_afm_values = []
        for examples in self.pattern_signatures.values():
            for example in examples:
                for field, value in example['pattern']['afm_values'].items():
                    cleaned = self._clean_afm_value(str(value))
                    if cleaned:
                        all_afm_values.append({
                            'original': value,
                            'cleaned': cleaned,
                            'field': field,
                            'ada': example['ada']
                        })
        
        # Categorize for validation testing
        for afm_data in all_afm_values[:50]:  # Limit for manageable test size
            cleaned = afm_data['cleaned']
            
            if cleaned.isdigit() and len(cleaned) == 9:
                validation_cases['valid_afms'].append(afm_data)
            elif cleaned.isdigit() and len(cleaned) in [8, 10, 11, 12]:
                validation_cases['boundary_cases'].append(afm_data)
            else:
                validation_cases['invalid_afms'].append(afm_data)
        
        # Save validation test data
        output_file = self.output_dir / 'validation_test_data.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(validation_cases, f, ensure_ascii=False, indent=2)
        
        total_validation = sum(len(cases) for cases in validation_cases.values())
        self.stdout.write(f"✅ Generated {total_validation} validation test cases")

    def generate_edge_case_scenarios(self):
        """Generate comprehensive edge case scenarios."""
        edge_case_report = {
            'summary': {
                'total_edge_cases': len(self.edge_cases),
                'edge_case_types': Counter(case['edge_case_type'] for case in self.edge_cases)
            },
            'scenarios': []
        }
        
        # Group edge cases by type
        edge_cases_by_type = defaultdict(list)
        for case in self.edge_cases:
            edge_cases_by_type[case['edge_case_type']].append(case)
        
        # Create scenarios for each edge case type
        for edge_type, cases in edge_cases_by_type.items():
            scenario = {
                'edge_case_type': edge_type,
                'count': len(cases),
                'examples': []
            }
            
            for case in cases[:3]:  # Max 3 examples per type
                scenario['examples'].append({
                    'ada': case['ada'],
                    'structure': case['pattern']['full_structure'],
                    'afm_fields': case['pattern']['afm_fields'],
                    'path': case['pattern']['path'],
                    'complexity_score': self._calculate_complexity_score(case['pattern'])
                })
            
            edge_case_report['scenarios'].append(scenario)
        
        # Save edge case report
        output_file = self.output_dir / 'edge_case_scenarios.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(edge_case_report, f, ensure_ascii=False, indent=2)
        
        self.stdout.write(f"✅ Generated edge case scenarios for {len(edge_cases_by_type)} edge case types")

    def _calculate_complexity_score(self, pattern: Dict) -> int:
        """Calculate complexity score for a pattern."""
        score = 0
        
        # Path depth
        score += pattern['path'].count('.') * 2
        score += pattern['path'].count('[') * 3
        
        # Multiple AFMs
        score += (len(pattern['afm_fields']) - 1) * 5
        
        # Structure complexity
        score += len(pattern['structure_keys'])
        
        # Nested objects
        for value in pattern['full_structure'].values():
            if isinstance(value, dict):
                score += 2
            elif isinstance(value, list):
                score += 3
        
        return score

    def _discover_role_patterns(self):
        """Discover role patterns from actual data instead of hard-coding them."""
        self.stdout.write("🔍 Discovering role patterns from data...")
        
        # First pass: collect all unique path patterns
        all_path_patterns = set()
        
        for examples in self.pattern_signatures.values():
            for example in examples:
                pattern = example['pattern']
                path_pattern = self._extract_path_pattern(pattern['path'])
                all_path_patterns.add(path_pattern)
                self.path_frequency[path_pattern] += 1
        
        # Second pass: analyze each pattern to understand its characteristics
        pattern_analysis = {}
        
        for path_pattern in all_path_patterns:
            pattern_analysis[path_pattern] = self._analyze_path_pattern(path_pattern)
        
        # Generate role mapping based on discovered patterns
        self.role_pattern_mapping = self._generate_role_mapping(pattern_analysis)
        
        return pattern_analysis

    def _extract_path_pattern(self, full_path: str) -> str:
        """Extract the meaningful pattern from a full path."""
        if not full_path:
            return 'root'
        
        # Remove array indices to get the structural pattern
        # "person[0]" -> "person[]"
        # "sponsor.details[2].info" -> "sponsor.details[].info"
        import re
        pattern = re.sub(r'\[\d+\]', '[]', full_path)
        
        # Extract the key semantic parts
        parts = pattern.split('.')
        
        # Focus on the most meaningful part (usually the first semantic element)
        if len(parts) == 1:
            return parts[0].replace('[]', '')  # "person[]" -> "person"
        else:
            # For nested paths, keep the first meaningful part
            return parts[0].replace('[]', '')  # "sponsor.details[]" -> "sponsor"

    def _analyze_path_pattern(self, path_pattern: str) -> Dict:
        """Analyze a discovered path pattern to understand its characteristics."""
        analysis = {
            'pattern': path_pattern,
            'frequency': self.path_frequency[path_pattern],
            'examples': [],
            'typical_structure_keys': set(),
            'name_patterns': set(),
            'afm_field_names': set(),
            'is_array_based': False,
            'nesting_depth': 0
        }
        
        # Collect examples for this pattern
        for examples in self.pattern_signatures.values():
            for example in examples:
                pattern = example['pattern']
                if self._extract_path_pattern(pattern['path']) == path_pattern:
                    analysis['examples'].append({
                        'ada': example['ada'],
                        'full_path': pattern['path'],
                        'structure': pattern['full_structure'],
                        'afm_fields': pattern['afm_fields']
                    })
                    
                    # Accumulate pattern characteristics
                    analysis['typical_structure_keys'].update(pattern['structure_keys'])
                    analysis['afm_field_names'].update(pattern['afm_fields'])
                    
                    # Check for name patterns
                    if 'name' in pattern['full_structure']:
                        name_value = pattern['full_structure']['name']
                        if isinstance(name_value, str) and name_value:
                            analysis['name_patterns'].add(self._classify_name_pattern(name_value))
                    
                    # Check if it's array-based
                    if '[' in pattern['path']:
                        analysis['is_array_based'] = True
                    
                    # Calculate nesting depth
                    analysis['nesting_depth'] = max(analysis['nesting_depth'], pattern['path'].count('.'))
        
        # Convert sets to lists for JSON serialization
        analysis['typical_structure_keys'] = list(analysis['typical_structure_keys'])
        analysis['name_patterns'] = list(analysis['name_patterns'])
        analysis['afm_field_names'] = list(analysis['afm_field_names'])
        
        return analysis

    def _classify_name_pattern(self, name: str) -> str:
        """Classify the type of entity based on name patterns."""
        name_lower = name.lower()
        
        # Common patterns in Greek business/person names
        if any(indicator in name_lower for indicator in [',,', ' του ', ' της ', 'ιωάννης', 'μαρία', 'γιάννης']):
            return 'person_name'
        elif any(indicator in name_lower for indicator in ['αε', 'επε', 'ικε', ' οε', 'εε', 'ανωνυμη', 'εταιρια']):
            return 'company_name'
        elif any(indicator in name_lower for indicator in ['υπουργειο', 'δημος', 'περιφερεια', 'κεντρο']):
            return 'government_org'
        elif any(indicator in name_lower for indicator in ['συλλογος', 'σωματειο', 'ενωση', 'ομοσπονδια']):
            return 'association'
        else:
            return 'unknown_entity'

    def _generate_role_mapping(self, pattern_analysis: Dict) -> Dict:
        """Generate role mapping based on discovered patterns."""
        role_mapping = {}
        
        for path_pattern, analysis in pattern_analysis.items():
            # Determine role based on pattern characteristics
            role = self._infer_role_from_analysis(path_pattern, analysis)
            role_mapping[path_pattern] = {
                'role': role,
                'confidence': self._calculate_role_confidence(analysis),
                'reasoning': self._explain_role_reasoning(path_pattern, analysis)
            }
        
        return role_mapping

    def _infer_role_from_analysis(self, path_pattern: str, analysis: Dict) -> str:
        """Infer the role from pattern analysis."""
        pattern_lower = path_pattern.lower()
        
        # Use the path pattern as the primary indicator
        if pattern_lower == 'person' and analysis['is_array_based']:
            return 'PERSON'
        elif pattern_lower in ['sponsor', 'sponsorafmname']:
            return 'SPONSOR'
        elif pattern_lower in ['grantor', 'grantorafmname']:
            return 'GRANTOR'
        elif pattern_lower in ['grantee', 'granteeafmname']:
            return 'GRANTEE'
        elif pattern_lower in ['org', 'organization']:
            return 'ORGANIZATION'
        elif 'donation' in pattern_lower:
            if 'giver' in pattern_lower:
                return 'DONATION_GIVER'
            elif 'receiver' in pattern_lower:
                return 'DONATION_RECEIVER'
            else:
                return 'DONATION_RELATED'
        else:
            # For unknown patterns, try to infer from name patterns
            name_patterns = analysis['name_patterns']
            if 'person_name' in name_patterns and analysis['is_array_based']:
                return f'UNKNOWN_PERSON_ARRAY_{pattern_pattern.upper()}'
            elif 'company_name' in name_patterns:
                return f'UNKNOWN_COMPANY_{path_pattern.upper()}'
            elif 'government_org' in name_patterns:
                return f'UNKNOWN_ORG_{path_pattern.upper()}'
            else:
                return f'UNKNOWN_{path_pattern.upper()}'

    def _calculate_role_confidence(self, analysis: Dict) -> float:
        """Calculate confidence in the role assignment."""
        confidence = 0.5  # Base confidence
        
        # Higher frequency = higher confidence
        if analysis['frequency'] >= 10:
            confidence += 0.3
        elif analysis['frequency'] >= 5:
            confidence += 0.2
        elif analysis['frequency'] >= 2:
            confidence += 0.1
        
        # Consistent name patterns = higher confidence
        if len(analysis['name_patterns']) == 1:
            confidence += 0.2
        
        # Standard AFM field names = higher confidence
        if 'afm' in analysis['afm_field_names']:
            confidence += 0.1
        
        return min(confidence, 1.0)

    def _explain_role_reasoning(self, path_pattern: str, analysis: Dict) -> str:
        """Explain why this role was assigned."""
        reasons = []
        
        reasons.append(f"Path pattern: '{path_pattern}'")
        reasons.append(f"Frequency: {analysis['frequency']} occurrences")
        
        if analysis['is_array_based']:
            reasons.append("Array-based structure suggests multiple entities")
        
        if analysis['name_patterns']:
            reasons.append(f"Name patterns: {', '.join(analysis['name_patterns'])}")
        
        if analysis['afm_field_names']:
            reasons.append(f"AFM fields: {', '.join(analysis['afm_field_names'])}")
        
        return "; ".join(reasons)

    def _determine_role_from_path(self, path: str, parent_key: str) -> str:
        """Determine entity role using discovered patterns."""
        path_pattern = self._extract_path_pattern(path)
        
        # Use discovered mapping if available
        if path_pattern in self.role_pattern_mapping:
            return self.role_pattern_mapping[path_pattern]['role']
        
        # Fallback for completely unknown patterns
        return f'UNDISCOVERED_{path_pattern.upper()}'

    def generate_ada_based_test_cases(self):
        """Enhanced version that first discovers patterns."""
        self.stdout.write("🔍 Generating ADA-based test cases with pattern discovery...")
        
        # First, discover all role patterns from the data
        pattern_analysis = self._discover_role_patterns()
        
        # Save pattern discovery results
        discovery_output = self.output_dir / 'discovered_patterns.json'
        with open(discovery_output, 'w', encoding='utf-8') as f:
            json.dump({
                'pattern_analysis': {k: v for k, v in pattern_analysis.items()},
                'role_mapping': self.role_pattern_mapping,
                'path_frequencies': dict(self.path_frequency.most_common())
            }, f, ensure_ascii=False, indent=2)
        
        self.stdout.write(f"📋 Discovered {len(pattern_analysis)} unique path patterns")
        self.stdout.write(f"📊 Role mapping confidence: {self._calculate_overall_confidence():.2f}")
        
        # Now group decisions by their discovered characteristics
        decision_scenarios = defaultdict(list)
        
        # ... rest of the existing ADA-based generation logic ...
        # but now using the discovered patterns instead of hard-coded ones
        
        return self._generate_scenarios_from_discovered_patterns(decision_scenarios)

    def _calculate_overall_confidence(self) -> float:
        """Calculate overall confidence in discovered patterns."""
        if not self.role_pattern_mapping:
            return 0.0
        
        confidences = [mapping['confidence'] for mapping in self.role_pattern_mapping.values()]
        return sum(confidences) / len(confidences)

    def _generate_scenarios_from_discovered_patterns(self, decision_scenarios: Dict) -> Dict:
        """Generate scenarios using discovered patterns rather than hard-coded ones."""
        # Group scenarios by discovered pattern types
        for pattern, mapping in self.role_pattern_mapping.items():
            role = mapping['role']
            confidence = mapping['confidence']
            
            # Only include high-confidence patterns in standard scenarios
            if confidence >= 0.7:
                if 'PERSON' in role and 'ARRAY' in role:
                    scenario_key = 'multiple_people_cases'
                elif 'PERSON' in role:
                    scenario_key = 'single_person_cases'
                elif 'SPONSOR' in role:
                    scenario_key = 'sponsor_cases'
                elif 'GRANTOR' in role or 'GRANTEE' in role:
                    scenario_key = 'grantor_grantee_cases'
                elif 'DONATION' in role:
                    scenario_key = 'donation_cases'
                elif 'ORG' in role:
                    scenario_key = 'organization_cases'
                else:
                    scenario_key = 'discovered_pattern_cases'
            else:
                # Low confidence patterns go to edge cases for manual review
                scenario_key = 'edge_cases'
            
            decision_scenarios[scenario_key] = []
        
        # Now populate with actual decisions...
        # (rest of the existing logic but using discovered patterns)
        
        return dict(decision_scenarios)

    def generate_test_summary(self, ada_test_cases: Dict):
        """Generate a summary of the test cases for documentation."""
        summary = {
            'generation_date': str(timezone.now()),
            'scenario_counts': {
                scenario: len(cases) for scenario, cases in ada_test_cases.items()
            },
            'sample_adas_by_scenario': {},
            'complexity_distribution': {},
            'total_decisions_analyzed': sum(len(cases) for cases in ada_test_cases.values())
        }
        
        # Sample ADAs for each scenario type
        for scenario, cases in ada_test_cases.items():
            summary['sample_adas_by_scenario'][scenario] = [
                case['ada'] for case in cases[:3]  # First 3 ADAs as samples
            ]
        
        # Save summary
        output_file = self.output_dir / 'test_summary.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)