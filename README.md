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

5. The enzyme works in the cytoplasm (found within intracellular anatomical structure).
```

## MCP (Model Context Protocol) Integration

This package provides MCP server integration, allowing AI assistants like Claude Desktop and ChatGPT to use GO Graph tools directly through the Model Context Protocol.

### Quick Setup

#### 1. Installation with MCP Support

```bash
# Install with MCP dependencies
pip install -e .
```

#### 2. Register with Claude Desktop

Use the built-in setup command to register the MCP server with Claude Desktop:

```bash
# Register server with Claude Desktop (default settings)
go_graph_setup claude-desktop

# Register with custom configuration
go_graph_setup claude-desktop --db-path "./my_go_db" --namespace "molecular_function" --force-rebuild

# Register with custom server name and Python path
go_graph_setup claude-desktop --server-name "my-go-tools" --python-path "/usr/bin/python3"

# Check registration status
go_graph_setup status
```

#### 3. Automatic Server Startup

The MCP server starts automatically when Claude Desktop or ChatGPT connects. There's no need to run it manually - the server will:

- Initialize the GO database on first startup (downloads GO data automatically)
- Use the configuration set during registration
- Log all activity to stderr (visible in Claude Desktop logs if needed)

#### 4. Manual Configuration (Optional)

If you prefer manual setup, add this to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "go-graph-mcp": {
      "command": "python",
      "args": ["-m", "go_graph_mcp.mcp.server"],
      "env": {}
    }
  }
}
```

#### 5. ChatGPT Configuration

Generate configuration for ChatGPT:

```bash
# Print configuration to stdout
go_graph_setup chatgpt-config

# Save to file
go_graph_setup chatgpt-config --output-file chatgpt_mcp_config.json
```

### MCP Server Configuration

The MCP server automatically initializes the GO database on startup based on environment variables. The database location and configuration are set once during server startup.

#### Configuration Options

Configure the server behavior using these options:

```bash
# Setup with custom database path and namespace
go_graph_setup claude-desktop --db-path "./my_go_db" --namespace "cellular_component"

# Setup with force rebuild on startup
go_graph_setup claude-desktop --db-path "./go_db" --force-rebuild
```

#### Environment Variables

The MCP server recognizes these environment variables:

- `GO_GRAPH_DB_PATH`: Database path (default: system temp directory)
- `GO_GRAPH_NAMESPACE`: GO namespace (default: `cellular_component`)
- `GO_GRAPH_FORCE_REBUILD`: Force rebuild database (default: `false`)
- `GO_GRAPH_AUTO_DOWNLOAD`: Auto download GO data (default: `true`)

### Available MCP Tools

Once configured, the following tools become available to AI assistants. Note that all tools use the database configured at server startup:

#### `search_go_terms`
Search GO terms with fuzzy matching and taxonomy filtering
- `query`: Search query string
- `limit`: Maximum results (default: 10)
- `min_score`: Minimum relevance score (default: 30.0)
- `include_taxa`: JSON string of taxa to include (e.g., '["mammals", "plants"]')
- `exclude_taxa`: JSON string of taxa to exclude (e.g., '["plants", "bacteria"]')

#### `get_go_term` 
Get specific GO term by ID
- `go_id`: GO identifier (e.g., "GO:0005737")

#### `get_go_term_relationships`
Get relationships for a GO term
- `go_id`: GO identifier
- `max_distance`: Maximum relationship distance (default: 3)

#### `get_database_stats`
Get database statistics and configuration info

#### `analyze_hashtag_terms`
Analyze hashtag terms in text
- `text`: Text containing hashtag terms (e.g., "The protein is in the #cytoplasm")

#### `augment_text`
Generate text variations by augmenting hashtag GO terms
- `text`: Text containing hashtag terms to augment
- `num_variations`: Number of variations to generate (default: 5)
- `synonym_probability`: Probability of using synonyms (default: 0.5)
- `definition_probability`: Probability of including definitions (default: 0.3)
- `go_id_probability`: Probability of including GO IDs (default: 0.2)
- `is_a_parent_probability`: Probability of including IS_A parent relationships (default: 0.3)
- `is_a_children_probability`: Probability of including IS_A children examples (default: 0.3)
- `part_of_parent_probability`: Probability of including PART_OF parent relationships (default: 0.3)
- `part_of_children_probability`: Probability of including PART_OF children examples (default: 0.3)
- `definition_max_length`: Maximum length for definitions as string (e.g., "40") (default: no truncation)

### Example Usage in Claude Desktop

Once MCP is configured, you can interact with GO Graph tools naturally. The database is automatically initialized when the server starts:

```
User: "what's the go id for outer mito membrane?"

Claude: I'll search for the GO term for "outer mitochondrial membrane" using the Gene Ontology database.
The GO ID for the outer mitochondrial membrane is GO:0005741.
The official term name is "mitochondrial outer membrane" and it's defined as "The outer, i.e. cytoplasm-facing, lipid bilayer of the mitochondrial envelope." The term "outer mitochondrial membrane" is listed as a synonym for this GO term.


```

### Management Commands

```bash
# Check MCP server status
go_graph_setup status

# Remove MCP server configuration
go_graph_setup remove --server-name "go-graph-mcp"

# Force removal without confirmation
go_graph_setup remove --server-name "go-graph-mcp" --force
```

### Troubleshooting

1. **"MCP server not found"**: Ensure you've restarted Claude Desktop completely after configuration
2. **"Python module not found"**: Verify the package is installed and the Python path is correct
3. **"Permission denied"**: Check that the Claude config directory is writable
4. **"Invalid JSON"**: Use `go_graph_setup status` to validate your configuration

For detailed MCP protocol information, visit: https://modelcontextprotocol.io

## Taxonomy Filtering

The system supports taxonomy constraints to filter GO terms by organism:

```bash
# Include only mammalian terms
query_go search --database ./go_db.kz --include-taxa "mammals" "chloroplast"

# Exclude plant terms  
query_go search --database ./go_db.kz --exclude-taxa "plants" "photosynthesis"

# Multiple taxa constraints
query_go search --database ./go_db.kz --include-taxa "mammals" "vertebrates" --exclude-taxa "bacteria" "virus" "metabolism"
```

The taxonomy filtering uses NCBI taxonomy and supports hierarchical constraint propagation - child terms of taxonomy-constrained parents are automatically filtered out.