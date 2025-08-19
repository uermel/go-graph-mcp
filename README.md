# skuzu

A Python package with src/skuzu organization.

## Installation

Using pip:
```bash
pip install .
```

Development installation:
```bash
pip install -e ".[dev]"
```

Using Hatch:
```bash
hatch build
```

## Usage

```python
import skuzu
print(skuzu.__version__)
```

### Gene Ontology Parser

The package includes a module for parsing Gene Ontology (GO) data into a KuzuDB graph database.

#### Command Line Usage

```bash
# Parse GO cellular component data into a KuzuDB database
skuzu parse-go --input data/go-basic.json --output ./go_db

# Parse a different GO namespace
skuzu parse-go --input data/go-basic.json --output ./go_db --namespace biological_process
```

#### Python API Usage

```python
from skuzu.go_parser import GOParser

# Initialize the parser with the output database path
parser = GOParser("./go_db")

# Parse GO data
parser.parse_go_json("data/go-basic.json", namespace="cellular_component")

# Close the connection
parser.close()
```

## Development

This project uses [Hatch](https://hatch.pypa.io/) for package management and building.

### Development Tools

This project uses several development tools:

- **pytest**: For running tests
- **black**: For code formatting
- **ruff**: For code linting
- **pre-commit**: For managing git hooks

To install development dependencies:
```bash
pip install -e ".[dev]"
```

To set up pre-commit:
```bash
pre-commit install
```

To run tests:
```bash
pytest
```

To format code:
```bash
black .
```

To lint code:
```bash
ruff .
``` 