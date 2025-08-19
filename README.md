# GO Graph

A Python package for parsing Gene Ontology (GO) data into KuzuDB graph database and providing fuzzy search capabilities with text augmentation.

## Installation

```bash
pip install -e .
```

## API Usage

### Basic Client Usage

```python
from go_graph_mcp.client import GOClient

# Connect to database
with GOClient("path/to/kuzu_db.kz") as client:
    # Search for terms
    results = client.search_terms("cytoplasm", limit=5)
    for result in results:
        print(f"{result.term.accession}: {result.term.name} (score: {result.score})")
    
    # Get specific term
    term = client.get_term_by_id("GO:0005737")
    print(f"Name: {term.name}")
    print(f"Definition: {term.definition}")
    
    # Get relationships
    relationships = client.get_all_related_terms("GO:0005737")
    print(f"IS_A parents: {len(relationships['is_a_parents'])}")
    print(f"PART_OF children: {len(relationships['part_of_children'])}")
```

### Text Augmentation

```python
from go_graph_mcp.client import GOClient, GOTextAugmentor, AugmentationOptions

with GOClient("path/to/kuzu_db.kz") as client:
    augmentor = GOTextAugmentor(client)
    
    # Configure augmentation options
    options = AugmentationOptions(
        num_variations=3,
        synonym_probability=0.6,
        definition_probability=0.4,
        is_a_parent_probability=0.3,
        part_of_children_probability=0.2
    )
    
    # Generate variations
    text = "The protein localizes to the #cytoplasm and #nucleus."
    variations = augmentor.augment_text(text, options)
    
    for i, variation in enumerate(variations, 1):
        print(f"{i}. {variation}")
```

## CLI Usage

### Database Setup

First, create and populate the KuzuDB database with GO data:

```bash
# Parse GO data into KuzuDB (downloads automatically if no input file specified)
parse_go parse --output ./go_db.kz --namespace cellular_component
```

Or specify a local GO JSON file:

```bash
# Use local file
parse_go parse --output ./go_db.kz --input go-basic.json --namespace cellular_component
```

### Basic Queries

```bash
# Search for terms
query_go search --database ./go_db.kz "mitochondr"

# Get specific term details  
query_go get-term --database ./go_db.kz GO:0005739

# Show relationships
query_go relationships --database ./go_db.kz GO:0005737

# Database statistics
query_go stats --database ./go_db.kz
```

### Text Augmentation

```bash
# Basic text augmentation
query_go augment-text --database ./go_db.kz \
  "The protein is found in the #cytoplasm and #mitochondria."

# Advanced augmentation with fine-grained control
query_go augment-text --database ./go_db.kz \
  --num-variations 5 \
  --synonym-prob 0.7 \
  --definition-prob 0.4 \
  --is-a-parent-prob 0.5 \
  --is-a-children-prob 0.2 \
  --part-of-parent-prob 0.3 \
  --part-of-children-prob 0.1 \
  --definition-max-length 100 \
  "Cellular processes occur in the #cytoplasm and #organelles."

# Analyze hashtag terms in text
query_go analyze-hashtags --database ./go_db.kz \
  "Research focuses on #autophagy and #endocytosis."
```

### Available Augmentation Options

- `--num-variations`: Number of text variations to generate (default: 5)
- `--synonym-prob`: Probability of using synonyms (0.0-1.0, default: 0.5)
- `--definition-prob`: Probability of including definitions (0.0-1.0, default: 0.3)  
- `--go-id-prob`: Probability of including GO IDs (0.0-1.0, default: 0.2)
- `--is-a-parent-prob`: Probability of including IS_A parent relationships (default: 0.3)
- `--is-a-children-prob`: Probability of including IS_A children examples (default: 0.3)
- `--part-of-parent-prob`: Probability of including PART_OF parent relationships (default: 0.3)
- `--part-of-children-prob`: Probability of including PART_OF children examples (default: 0.3)
- `--definition-max-length`: Maximum length for definitions (default: no truncation)
- `--relationship-prob`: Legacy option - overrides individual relationship probabilities if set

## Example Output

### Search Results
```
$ query_go search --database ./go_db.kz "cytosol"

Found 10 results for 'cytosol':

1. GO:0005829 - cytosol
   Score: 100.0 (matched via exact: 'cytosol')
   Definition: The part of the cytoplasm that does not contain organelles but which does contain other particulate ...

2. GO:0000345 - cytosolic DNA-directed RNA polymerase complex
   Score: 100.0 (matched via name: 'cytosolic DNA-directed RNA polymerase complex')
   Definition: The eubacterial DNA-directed RNA polymerase is a multisubunit complex with a core composed of the es...
...
```

### Text Augmentation Results
```
$ query_go augment-text --database ./go_db.kz "The enzyme works in the #cytoplasm."
Generated 5 variations:
==================================================

1. The enzyme works in the cytoplasm (The contents of a cell excluding the plasma membrane and nucleus, but including other subcellular structures.; has subtypes including ectoplasm, cell cortex region, and germ plasm).

2. The enzyme works in the cytoplasm (includes examples like yolk plasma, plastid thylakoid, and Golgi ribbon).

3. The enzyme works in the cytoplasm (includes structures like Dbf2p-Mob1p complex, Rab-protein geranylgeranyltransferase complex, and GARP complex).

4. The enzyme works in the cytoplasm (GO:0005737; The contents of a cell excluding the plasma membrane and nucleus, but including other subcellular structures.).

5. The enzyme works in the cytoplasm (found within intracellular anatomical structure).```