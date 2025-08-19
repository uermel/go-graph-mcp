"""Taxonomy filtering for GO terms using NCBI taxonomy data."""

import re
from typing import List, Set, Optional, Dict
from ete3 import NCBITaxa

class TaxonomyFilter:
    """Filter GO terms based on NCBI taxonomy constraints."""
    
    def __init__(self):
        """Initialize the taxonomy filter with NCBI taxonomy database."""
        self.ncbi = NCBITaxa()
        
    def parse_taxon_id(self, taxon_constraint: str) -> Optional[int]:
        """Parse NCBI taxon ID from constraint string.
        
        Args:
            taxon_constraint: String like 'NCBITaxon:40674' or just '40674'
            
        Returns:
            NCBI taxon ID as integer, or None if invalid
        """
        if not taxon_constraint:
            return None
            
        # Handle different formats: NCBITaxon:40674, 40674, etc.
        match = re.search(r'(\d+)', taxon_constraint)
        if match:
            return int(match.group(1))
        return None
    
    def get_taxon_lineage(self, taxon_id: int) -> List[int]:
        """Get complete lineage for a taxon ID.
        
        Args:
            taxon_id: NCBI taxon ID
            
        Returns:
            List of taxon IDs from root to the specified taxon
        """
        try:
            lineage = self.ncbi.get_lineage(taxon_id)
            return lineage if lineage else []
        except Exception:
            return []
    
    def get_taxon_name(self, taxon_id: int) -> Optional[str]:
        """Get scientific name for a taxon ID.
        
        Args:
            taxon_id: NCBI taxon ID
            
        Returns:
            Scientific name or None if not found
        """
        try:
            names = self.ncbi.get_taxid_translator([taxon_id])
            return names.get(taxon_id)
        except Exception:
            return None
    
    def get_descendants(self, taxon_id: int) -> Set[int]:
        """Get all descendant taxon IDs for a given taxon.
        
        Args:
            taxon_id: NCBI taxon ID
            
        Returns:
            Set of descendant taxon IDs
        """
        try:
            descendants = self.ncbi.get_descendant_taxa(taxon_id, intermediate_nodes=True)
            return set(descendants) if descendants else set()
        except Exception:
            return set()
    
    def is_taxon_in_lineage(self, query_taxon: int, constraint_taxon: int) -> bool:
        """Check if a query taxon is in the lineage of a constraint taxon.
        
        Args:
            query_taxon: Taxon ID to check
            constraint_taxon: Constraint taxon ID
            
        Returns:
            True if query_taxon is in the lineage of constraint_taxon
        """
        if query_taxon == constraint_taxon:
            return True
            
        lineage = self.get_taxon_lineage(query_taxon)
        return constraint_taxon in lineage
    
    def resolve_taxon_name_to_id(self, taxon_name: str) -> Optional[int]:
        """Resolve a taxon name to NCBI taxon ID.
        
        Args:
            taxon_name: Scientific or common name (e.g., 'Mammalia', 'mammals')
            
        Returns:
            NCBI taxon ID or None if not found
        """
        try:
            # Try exact match first
            taxon_dict = self.ncbi.get_name_translator([taxon_name])
            if taxon_name in taxon_dict:
                return taxon_dict[taxon_name][0]
                
            # Try case-insensitive search
            taxon_name_lower = taxon_name.lower()
            
            # Common mappings
            common_names = {
                'plants': 33090,      # Viridiplantae (green plants)
                'plant': 33090,
                'animals': 33208,     # Metazoa (animals)
                'animal': 33208,
                'mammals': 40674,     # Mammalia
                'mammal': 40674,
                'bacteria': 2,        # Bacteria
                'archaea': 2157,      # Archaea
                'fungi': 4751,        # Fungi
                'fungus': 4751,
                'vertebrates': 7742,  # Vertebrata
                'vertebrate': 7742,
                'insects': 6960,      # Hexapoda
                'insect': 6960,
            }
            
            if taxon_name_lower in common_names:
                return common_names[taxon_name_lower]
                
            return None
        except Exception:
            return None


class TaxonomyConstraint:
    """Represents a single taxonomy constraint for a GO term."""
    
    def __init__(self, constraint_type: str, taxon_id: int, taxon_name: Optional[str] = None):
        """Initialize taxonomy constraint.
        
        Args:
            constraint_type: 'in_taxon' or 'never_in_taxon'
            taxon_id: NCBI taxon ID
            taxon_name: Optional human-readable taxon name
        """
        self.constraint_type = constraint_type
        self.taxon_id = taxon_id
        self.taxon_name = taxon_name
    
    def __str__(self) -> str:
        name_part = f" ({self.taxon_name})" if self.taxon_name else ""
        return f"{self.constraint_type}: {self.taxon_id}{name_part}"


class TaxonomyFilterOptions:
    """Options for filtering GO terms by taxonomy."""
    
    def __init__(
        self,
        include_taxa: Optional[List[str]] = None,
        exclude_taxa: Optional[List[str]] = None,
        enforce_go_constraints: bool = True
    ):
        """Initialize taxonomy filter options.
        
        Args:
            include_taxa: List of taxa to include (taxon names or IDs)
            exclude_taxa: List of taxa to exclude (taxon names or IDs)  
            enforce_go_constraints: Whether to enforce GO's built-in taxon constraints
        """
        self.include_taxa = include_taxa or []
        self.exclude_taxa = exclude_taxa or []
        self.enforce_go_constraints = enforce_go_constraints
    
    def has_constraints(self) -> bool:
        """Check if any constraints are specified."""
        return bool(self.include_taxa or self.exclude_taxa or self.enforce_go_constraints)