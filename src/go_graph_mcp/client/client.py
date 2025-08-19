"""GO Client for querying KuzuDB with fuzzy matching and graph traversal."""

import os
from typing import List, Optional, Tuple
from pathlib import Path

import kuzu
from rapidfuzz import fuzz

from .models import GOTerm, SearchResult, RelationshipResult


class GOClient:
    """Client for querying GO terms from KuzuDB with fuzzy matching."""
    
    def __init__(self, db_path: str):
        """Initialize the GO client.
        
        Args:
            db_path: Path to the KuzuDB database directory
            
        Raises:
            FileNotFoundError: If the database directory doesn't exist
            RuntimeError: If unable to connect to the database
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database path not found: {db_path}")
        
        self.db_path = db_path
        try:
            self.db = kuzu.Database(db_path, read_only=True)
            self.conn = kuzu.Connection(self.db)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to database: {e}")
    
    def close(self):
        """Close the database connection."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def get_term_by_id(self, go_id: str) -> Optional[GOTerm]:
        """Get a GO term by its exact ID.
        
        Args:
            go_id: GO identifier (e.g., "GO:0005737")
            
        Returns:
            GOTerm if found, None otherwise
        """
        try:
            # Get the term
            result = self.conn.execute("""
                MATCH (t:GOTerm {id: $id})
                RETURN t.id, t.name, t.namespace, t.definition, t.comment
            """, {"id": go_id})
            
            if not result.has_next():
                return None
            
            row = result.get_next()
            term_data = {
                "accession": row[0],
                "name": row[1] or "",
                "namespace": row[2],
                "definition": row[3] or "",
                "comment": row[4] or ""
            }
            
            # Get synonyms
            syn_result = self.conn.execute("""
                MATCH (s:Synonym {term_id: $id})
                RETURN s.synonym
            """, {"id": go_id})
            
            synonyms = []
            while syn_result.has_next():
                syn_row = syn_result.get_next()
                synonyms.append(syn_row[0])
            
            term_data["synonyms"] = synonyms
            
            return GOTerm(**term_data)
            
        except Exception as e:
            print(f"Error retrieving term {go_id}: {e}")
            return None
    
    def search_terms(self, query: str, limit: int = 10, min_score: float = 30.0) -> List[SearchResult]:
        """Search for GO terms using fuzzy matching.
        
        Args:
            query: Search query
            limit: Maximum number of results to return
            min_score: Minimum relevance score (0-100)
            
        Returns:
            List of SearchResult objects ordered by relevance
        """
        if not query.strip():
            return []
        
        query = query.strip().lower()
        results = []
        
        try:
            # Search in term names
            name_result = self.conn.execute("""
                MATCH (t:GOTerm)
                RETURN t.id, t.name, t.namespace, t.definition, t.comment
            """)
            
            # Collect all terms for fuzzy matching
            terms_data = []
            while name_result.has_next():
                row = name_result.get_next()
                terms_data.append({
                    "accession": row[0],
                    "name": row[1] or "",
                    "namespace": row[2],
                    "definition": row[3] or "",
                    "comment": row[4] or ""
                })
            
            # Get all synonyms
            synonyms_map = {}
            syn_result = self.conn.execute("""
                MATCH (s:Synonym)
                RETURN s.term_id, s.synonym
            """)
            
            while syn_result.has_next():
                syn_row = syn_result.get_next()
                term_id = syn_row[0]
                synonym = syn_row[1]
                if term_id not in synonyms_map:
                    synonyms_map[term_id] = []
                synonyms_map[term_id].append(synonym)
            
            # First pass: Find exact matches
            exact_matches = []
            fuzzy_candidates = []
            
            for term_data in terms_data:
                term_id = term_data["accession"]
                name = term_data["name"]
                synonyms = synonyms_map.get(term_id, [])
                
                # Add synonyms to term data
                term_data["synonyms"] = synonyms
                
                # Check for exact name match
                if query.lower() == name.lower():
                    exact_matches.append(SearchResult(
                        term=GOTerm(**term_data),
                        score=100.0,
                        match_type="exact",
                        matched_text=name
                    ))
                    continue
                
                # Check for exact synonym match
                exact_synonym_match = None
                for synonym in synonyms:
                    if query.lower() == synonym.lower():
                        exact_synonym_match = synonym
                        break
                
                if exact_synonym_match:
                    exact_matches.append(SearchResult(
                        term=GOTerm(**term_data),
                        score=100.0,  # Same as exact name match
                        match_type="exact",
                        matched_text=exact_synonym_match
                    ))
                    continue
                
                # Add to fuzzy candidates for second pass
                fuzzy_candidates.append(term_data)
            
            # Second pass: Fuzzy matching only if we don't have enough exact matches
            fuzzy_matches = []
            remaining_slots = limit - len(exact_matches)
            
            if remaining_slots > 0:
                for term_data in fuzzy_candidates:
                    term_id = term_data["accession"]
                    name = term_data["name"]
                    synonyms = term_data["synonyms"]
                    
                    best_score = 0.0
                    best_match = ""
                    best_type = "name"
                    
                    # Fuzzy match against name
                    name_score = fuzz.partial_ratio(query, name.lower())
                    if name_score >= min_score and name_score > best_score:
                        best_score = name_score
                        best_match = name
                        best_type = "name"
                    
                    # Fuzzy match against synonyms
                    for synonym in synonyms:
                        score = fuzz.partial_ratio(query, synonym.lower())
                        if score >= min_score and score > best_score:
                            best_score = score
                            best_match = synonym
                            best_type = "synonym"
                    
                    # Add the best fuzzy match for this term
                    if best_score >= min_score:
                        fuzzy_matches.append(SearchResult(
                            term=GOTerm(**term_data),
                            score=float(best_score),
                            match_type=best_type,
                            matched_text=best_match
                        ))
                
                # Sort fuzzy matches by score
                fuzzy_matches.sort(key=lambda x: x.score, reverse=True)
                fuzzy_matches = fuzzy_matches[:remaining_slots]
            
            # Combine results: exact matches first, then best fuzzy matches
            results = exact_matches + fuzzy_matches
            
            # Sort by score (highest first) and limit results
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:limit]
            
        except Exception as e:
            print(f"Error searching for terms: {e}")
            return []
    
    def get_is_a_parents(self, go_id: str, max_distance: int = 5) -> List[RelationshipResult]:
        """Get parent terms through IS_A relationships.
        
        Args:
            go_id: GO identifier
            max_distance: Maximum relationship distance to traverse
            
        Returns:
            List of RelationshipResult objects
        """
        return self._get_related_terms(go_id, "IS_A", "outgoing", max_distance)
    
    def get_is_a_children(self, go_id: str, max_distance: int = 5) -> List[RelationshipResult]:
        """Get child terms through IS_A relationships.
        
        Args:
            go_id: GO identifier
            max_distance: Maximum relationship distance to traverse
            
        Returns:
            List of RelationshipResult objects
        """
        return self._get_related_terms(go_id, "IS_A", "incoming", max_distance)
    
    def get_part_of_parents(self, go_id: str, max_distance: int = 5) -> List[RelationshipResult]:
        """Get parent terms through PART_OF relationships.
        
        Args:
            go_id: GO identifier
            max_distance: Maximum relationship distance to traverse
            
        Returns:
            List of RelationshipResult objects
        """
        return self._get_related_terms(go_id, "PART_OF", "outgoing", max_distance)
    
    def get_part_of_children(self, go_id: str, max_distance: int = 5) -> List[RelationshipResult]:
        """Get child terms through PART_OF relationships.
        
        Args:
            go_id: GO identifier
            max_distance: Maximum relationship distance to traverse
            
        Returns:
            List of RelationshipResult objects
        """
        return self._get_related_terms(go_id, "PART_OF", "incoming", max_distance)
    
    def get_all_related_terms(self, go_id: str, max_distance: int = 3) -> dict:
        """Get all related terms (both IS_A and PART_OF, in both directions).
        
        Args:
            go_id: GO identifier
            max_distance: Maximum relationship distance to traverse
            
        Returns:
            Dictionary with keys: is_a_parents, is_a_children, part_of_parents, part_of_children
        """
        return {
            "is_a_parents": self.get_is_a_parents(go_id, max_distance),
            "is_a_children": self.get_is_a_children(go_id, max_distance),
            "part_of_parents": self.get_part_of_parents(go_id, max_distance),
            "part_of_children": self.get_part_of_children(go_id, max_distance)
        }
    
    def _get_related_terms(self, go_id: str, relationship_type: str, direction: str, max_distance: int) -> List[RelationshipResult]:
        """Internal method to get related terms through graph traversal.
        
        Args:
            go_id: GO identifier
            relationship_type: "IS_A" or "PART_OF"
            direction: "outgoing" or "incoming"
            max_distance: Maximum relationship distance
            
        Returns:
            List of RelationshipResult objects
        """
        try:
            results = []
            
            # Build the query based on direction
            if direction == "outgoing":
                # Get terms this term points to (parents)
                query = f"""
                    MATCH path = (start:GOTerm {{id: $start_id}})-[:{relationship_type}*1..{max_distance}]->(related:GOTerm)
                    RETURN related.id, related.name, related.namespace, related.definition, related.comment, length(path) as distance
                """
            else:
                # Get terms that point to this term (children)
                query = f"""
                    MATCH path = (related:GOTerm)-[:{relationship_type}*1..{max_distance}]->(start:GOTerm {{id: $start_id}})
                    RETURN related.id, related.name, related.namespace, related.definition, related.comment, length(path) as distance
                """
            
            result = self.conn.execute(query, {"start_id": go_id})
            
            # Collect unique terms (avoid duplicates from different paths)
            seen_terms = set()
            
            while result.has_next():
                row = result.get_next()
                term_id = row[0]
                
                if term_id in seen_terms:
                    continue
                seen_terms.add(term_id)
                
                # Get synonyms for this term
                syn_result = self.conn.execute("""
                    MATCH (s:Synonym {term_id: $id})
                    RETURN s.synonym
                """, {"id": term_id})
                
                synonyms = []
                while syn_result.has_next():
                    syn_row = syn_result.get_next()
                    synonyms.append(syn_row[0])
                
                term = GOTerm(
                    accession=term_id,
                    name=row[1] or "",
                    namespace=row[2],
                    definition=row[3] or "",
                    comment=row[4] or "",
                    synonyms=synonyms
                )
                
                results.append(RelationshipResult(
                    term=term,
                    relationship_type=relationship_type.lower(),
                    distance=row[5]
                ))
            
            # Sort by distance
            results.sort(key=lambda x: x.distance)
            return results
            
        except Exception as e:
            print(f"Error getting related terms for {go_id}: {e}")
            return []
    
    def get_database_stats(self) -> dict:
        """Get database statistics.
        
        Returns:
            Dictionary with term and relationship counts
        """
        try:
            stats = {}
            
            # Count GO terms
            result = self.conn.execute("MATCH (t:GOTerm) RETURN count(t) as count")
            if result.has_next():
                stats["go_terms"] = result.get_next()[0]
            
            # Count synonyms
            result = self.conn.execute("MATCH (s:Synonym) RETURN count(s) as count")
            if result.has_next():
                stats["synonyms"] = result.get_next()[0]
            
            # Count IS_A relationships
            result = self.conn.execute("MATCH ()-[r:IS_A]->() RETURN count(r) as count")
            if result.has_next():
                stats["is_a_relationships"] = result.get_next()[0]
            
            # Count PART_OF relationships
            result = self.conn.execute("MATCH ()-[r:PART_OF]->() RETURN count(r) as count")
            if result.has_next():
                stats["part_of_relationships"] = result.get_next()[0]
            
            return stats
            
        except Exception as e:
            print(f"Error getting database stats: {e}")
            return {}