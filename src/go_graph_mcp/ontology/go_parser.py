"""Module for parsing Gene Ontology (GO) data into KuzuDB."""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

import kuzu


class GOParser:
    """Parser for Gene Ontology data into KuzuDB."""

    def __init__(self, db_path: str):
        """Initialize the parser with a path to the KuzuDB database.

        Args:
            db_path: Path where the KuzuDB database will be stored
        """
        self.db_path = db_path
        self.db = None
        self.conn = None

    def init_database(self):
        """Initialize the KuzuDB database schema."""
        # Remove existing database directory if it exists
        if os.path.exists(self.db_path):
            shutil.rmtree(self.db_path)
        
        # Initialize the database (KuzuDB will create the directory)
        self.db = kuzu.Database(self.db_path)
        self.conn = kuzu.Connection(self.db)
        
        # Create schema for GO terms using Cypher
        self.conn.execute("""
            CREATE NODE TABLE GOTerm (
                id STRING,
                name STRING,
                namespace STRING,
                definition STRING,
                comment STRING,
                PRIMARY KEY (id)
            )
        """)
        
        # Create schema for synonyms
        self.conn.execute("""
            CREATE NODE TABLE Synonym (
                id STRING,
                term_id STRING,
                synonym STRING,
                PRIMARY KEY (id)
            )
        """)
        
        # Create schema for relationships between GO terms
        self.conn.execute("""
            CREATE REL TABLE IS_A (
                FROM GOTerm TO GOTerm
            )
        """)
        
        self.conn.execute("""
            CREATE REL TABLE PART_OF (
                FROM GOTerm TO GOTerm
            )
        """)

    def _extract_go_id(self, uri: str) -> str:
        """Extract the GO ID from a URI.
        
        Args:
            uri: URI of the form http://purl.obolibrary.org/obo/GO_XXXXXXX
            
        Returns:
            GO ID of the form GO:XXXXXXX
        """
        match = re.search(r'GO_(\d+)', uri)
        if match:
            return f"GO:{match.group(1)}"
        return uri

    def _get_namespace(self, term_data: Dict) -> Optional[str]:
        """Extract namespace from a term's metadata.
        
        Args:
            term_data: Term data dictionary
            
        Returns:
            Namespace string or None if not found
        """
        meta = term_data.get('meta', {})
        basic_props = meta.get('basicPropertyValues', [])
        
        for prop in basic_props:
            if prop.get('pred') == "http://www.geneontology.org/formats/oboInOwl#hasOBONamespace":
                return prop.get('val')
        
        return None

    def _extract_definition(self, term_data: Dict) -> str:
        """Extract definition from a term's metadata.
        
        Args:
            term_data: Term data dictionary
            
        Returns:
            Definition string or empty string if not found
        """
        meta = term_data.get('meta', {})
        definition = meta.get('definition', {})
        return definition.get('val', '')

    def _extract_comment(self, term_data: Dict) -> str:
        """Extract comment from a term's metadata.
        
        Args:
            term_data: Term data dictionary
            
        Returns:
            Comment string or empty string if not found
        """
        meta = term_data.get('meta', {})
        comments = meta.get('comments', [])
        if comments:
            return comments[0]
        return ''

    def _extract_synonyms(self, term_data: Dict) -> List[str]:
        """Extract synonyms from a term's metadata.
        
        Args:
            term_data: Term data dictionary
            
        Returns:
            List of synonym strings
        """
        synonyms = []
        meta = term_data.get('meta', {})
        
        # Extract from synonyms list
        synonym_list = meta.get('synonyms', [])
        for syn in synonym_list:
            if isinstance(syn, dict):
                val = syn.get('val', '')
                if val:
                    synonyms.append(val)
            elif isinstance(syn, str):
                synonyms.append(syn)
        
        # Extract from basicPropertyValues (alternate names)
        basic_props = meta.get('basicPropertyValues', [])
        for prop in basic_props:
            pred = prop.get('pred', '')
            val = prop.get('val', '')
            # Look for synonym-related predicates
            if 'synonym' in pred.lower() or 'altLabel' in pred:
                if val:
                    synonyms.append(val)
        
        return list(set(synonyms))  # Remove duplicates

    def _find_relationships(self, term_data: Dict) -> List[tuple]:
        """Find relationships to other terms.
        
        Args:
            term_data: Term data dictionary
            
        Returns:
            List of (relationship_type, target_id) tuples
        """
        relationships = []
        
        # Parse different relationship formats
        
        # Format 1: Direct edges
        if 'edges' in term_data:
            for edge in term_data.get('edges', []):
                pred = edge.get('pred', '')
                obj = edge.get('obj', '')
                
                # Skip non-GO relationships
                if 'GO_' not in obj:
                    continue
                    
                # Parse is_a relationship
                if pred == 'is_a' or pred == 'http://www.w3.org/2000/01/rdf-schema#subClassOf':
                    relationships.append(('is_a', self._extract_go_id(obj)))
                # Parse part_of relationship - match both part_of string and BFO_0000050
                elif 'part_of' in pred or 'BFO_0000050' in pred:
                    relationships.append(('part_of', self._extract_go_id(obj)))
        
        # Format 2: Meta > Subsets (older format)
        meta = term_data.get('meta', {})
        
        # Check for logical definitions that might contain relationships
        if 'logicalDefinitionAxioms' in meta:
            for axiom in meta.get('logicalDefinitionAxioms', []):
                for restriction in axiom.get('restrictions', []):
                    prop = restriction.get('property', '')
                    filler = restriction.get('filler', '')
                    
                    # Skip non-GO relationships
                    if 'GO_' not in filler:
                        continue
                        
                    if 'is_a' in prop:
                        relationships.append(('is_a', self._extract_go_id(filler)))
                    elif 'part_of' in prop or 'BFO_0000050' in prop:
                        relationships.append(('part_of', self._extract_go_id(filler)))
        
        # Check for relationship to other objects
        if 'relationship' in meta:
            for rel in meta.get('relationship', []):
                prop = rel.get('pred', '')
                obj = rel.get('val', '')
                
                # Skip non-GO relationships
                if not obj or 'GO:' not in obj:
                    continue
                    
                if 'is_a' in prop:
                    relationships.append(('is_a', obj))
                elif 'part_of' in prop or 'BFO_0000050' in prop:
                    relationships.append(('part_of', obj))
                    
        return relationships

    def _escape_cypher_string(self, text: str) -> str:
        """Properly escape a string for Cypher queries.
        
        Args:
            text: String to escape
            
        Returns:
            Escaped string safe for Cypher queries
        """
        if not text:
            return ""
        # Replace backslashes first to avoid double escaping
        text = text.replace('\\', '\\\\')
        # Replace single quotes with escaped single quotes
        text = text.replace("'", "\\'")
        return text

    def parse_go_json(self, json_path: str, namespace: str = "cellular_component", debug: bool = False):
        """Parse GO data from JSON and load it into KuzuDB.
        
        Args:
            json_path: Path to the GO JSON file
            namespace: GO namespace to filter for (default: cellular_component)
            debug: Enable additional debug output
        """
        if not self.db or not self.conn:
            self.init_database()
            
        print(f"Loading GO data from {json_path}...")
        
        # Load the GO data from JSON
        with open(json_path, 'r') as f:
            go_data = json.load(f)
            
        # Extract nodes from the graph
        go_terms = []
        if 'graphs' in go_data and len(go_data['graphs']) > 0:
            go_terms = go_data['graphs'][0].get('nodes', [])
            
            # Check edges section (might be separate from nodes)
            edges = go_data['graphs'][0].get('edges', [])
            if debug and edges:
                print(f"Found {len(edges)} edges in the graph structure")
                # Print first few edges for debugging
                for i, edge in enumerate(edges[:5]):
                    print(f"Edge {i}: {edge}")
        
        # Process terms
        namespace_terms = {}
        relationships = []
        
        print(f"Processing GO terms...")
        for term in go_terms:
            term_id = term.get('id', '')
            
            # Skip non-GO terms
            if 'GO_' not in term_id:
                continue
            
            # Extract GO ID
            go_id = self._extract_go_id(term_id)
            
            # Get term namespace
            term_namespace = self._get_namespace(term)
            
            # Skip terms not in target namespace
            if term_namespace != namespace:
                continue
                
            # Skip deprecated terms
            meta = term.get('meta', {})
            if meta.get('deprecated', False):
                continue
                
            # Store term data including synonyms
            synonyms = self._extract_synonyms(term)
            namespace_terms[go_id] = {
                'id': go_id,
                'name': term.get('lbl', ''),
                'namespace': term_namespace,
                'definition': self._extract_definition(term),
                'comment': self._extract_comment(term),
                'synonyms': synonyms
            }
            
            # Find relationships
            term_relationships = self._find_relationships(term)
            
            # Store the source of the relationship 
            for rel_type, target in term_relationships:
                relationships.append((go_id, target, rel_type))
        
        # Special handling: Process edges from the graph section if they exist
        if 'graphs' in go_data and len(go_data['graphs']) > 0 and 'edges' in go_data['graphs'][0]:
            edges = go_data['graphs'][0].get('edges', [])
            for edge in edges:
                sub = edge.get('sub', '')
                pred = edge.get('pred', '')
                obj = edge.get('obj', '')
                
                # Skip non-GO terms
                if 'GO_' not in sub or 'GO_' not in obj:
                    continue
                
                # Extract GO IDs
                source_id = self._extract_go_id(sub)
                target_id = self._extract_go_id(obj)
                
                # Skip terms not in our namespace
                if source_id not in namespace_terms:
                    continue
                
                # Determine relationship type
                if 'is_a' in pred or pred == 'http://www.w3.org/2000/01/rdf-schema#subClassOf':
                    relationships.append((source_id, target_id, 'is_a'))
                elif 'part_of' in pred or 'BFO_0000050' in pred:
                    relationships.append((source_id, target_id, 'part_of'))
        
        # Insert GO terms
        print(f"Inserting {len(namespace_terms)} {namespace} terms...")
        for term_id, term_data in namespace_terms.items():
            # Use parameters for safe insertion
            params = {
                'id': term_data['id'],
                'name': term_data['name'] or "",
                'namespace': term_data['namespace'] or "",
                'definition': term_data['definition'] or "",
                'comment': term_data['comment'] or ""
            }
            
            query = """
                MERGE (t:GOTerm {id: $id})
                SET t.name = $name,
                    t.namespace = $namespace,
                    t.definition = $definition,
                    t.comment = $comment
            """
            
            self.conn.execute(query, params)
        
        # Insert synonyms
        print(f"Inserting synonyms...")
        synonym_count = 0
        for term_id, term_data in namespace_terms.items():
            synonyms = term_data.get('synonyms', [])
            for idx, synonym in enumerate(synonyms):
                if synonym and synonym.strip():
                    synonym_id = f"{term_id}_{idx}"
                    self.conn.execute("""
                        CREATE (s:Synonym {id: $id, term_id: $term_id, synonym: $synonym})
                    """, {'id': synonym_id, 'term_id': term_id, 'synonym': synonym.strip()})
                    synonym_count += 1
        
        print(f"Inserted {synonym_count} synonyms")
        
        # Insert relationships
        print(f"Collecting relationships...")
        valid_relationships = []
        for source, target, rel_type in relationships:
            # Skip relationships to terms outside our namespace
            if target not in namespace_terms:
                continue
            valid_relationships.append((source, target, rel_type))
        
        # Process in batches for better performance
        batch_size = 1000
        relationship_batches = [valid_relationships[i:i + batch_size] 
                               for i in range(0, len(valid_relationships), batch_size)]
        
        print(f"Inserting {len(valid_relationships)} relationships in {len(relationship_batches)} batches...")
        
        for batch_idx, batch in enumerate(relationship_batches):
            print(f"Processing batch {batch_idx + 1}/{len(relationship_batches)}...")
            
            # Process IS_A relationships
            is_a_rels = [(source, target) for source, target, rel_type in batch if rel_type == "is_a"]
            if is_a_rels:
                for source, target in is_a_rels:
                    self.conn.execute("""
                        MATCH (source:GOTerm {id: $source}), (target:GOTerm {id: $target})
                        CREATE (source)-[:IS_A]->(target)
                    """, {'source': source, 'target': target})
            
            # Process PART_OF relationships
            part_of_rels = [(source, target) for source, target, rel_type in batch if rel_type == "part_of"]
            if part_of_rels:
                for source, target in part_of_rels:
                    self.conn.execute("""
                        MATCH (source:GOTerm {id: $source}), (target:GOTerm {id: $target})
                        CREATE (source)-[:PART_OF]->(target)
                    """, {'source': source, 'target': target})
        
        print(f"Successfully loaded {namespace} GO terms into KuzuDB")

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None 