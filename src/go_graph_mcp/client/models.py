"""Pydantic models for GO terms and search results."""

from typing import List, Optional
from pydantic import BaseModel, Field


class GOTerm(BaseModel):
    """Pydantic model for a Gene Ontology term."""
    
    accession: str = Field(..., description="GO accession identifier (e.g., GO:0005737)")
    name: str = Field(..., description="Term name")
    synonyms: List[str] = Field(default_factory=list, description="List of synonyms")
    definition: str = Field(default="", description="Term definition")
    comment: str = Field(default="", description="Additional comments")
    namespace: Optional[str] = Field(default=None, description="GO namespace")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
        extra = "forbid"


class SearchResult(BaseModel):
    """Search result with relevance scoring."""
    
    term: GOTerm = Field(..., description="The GO term")
    score: float = Field(..., description="Relevance score (0-100)")
    match_type: str = Field(..., description="Type of match: 'name', 'synonym', or 'exact'")
    matched_text: str = Field(..., description="The text that matched the search")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
        extra = "forbid"


class RelationshipResult(BaseModel):
    """Result containing related terms through graph relationships."""
    
    term: GOTerm = Field(..., description="The related GO term")
    relationship_type: str = Field(..., description="Type of relationship: 'is_a' or 'part_of'")
    distance: int = Field(..., description="Distance from the original term")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
        extra = "forbid"