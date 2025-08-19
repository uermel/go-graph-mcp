"""Text augmentation functionality for GO terms."""

import re
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .client import GOClient
from .models import GOTerm


# Text formulation banks for relationship descriptions
IS_A_PARENT_FORMULATIONS = [
    "a type of {parents}",
    "a kind of {parents}",
    "classified as {parents}",
    "categorized as {parents}",
    "a form of {parents}",
]

PART_OF_PARENT_FORMULATIONS = [
    "part of {parents}",
    "found within {parents}",
    "located in {parents}",
    "a component of {parents}",
    "contained within {parents}",
]

IS_A_CHILDREN_FORMULATIONS = [
    "includes examples such as {examples}",
    "encompasses types like {examples}",
    "has subtypes including {examples}",
    "includes varieties such as {examples}",
    "contains subtypes like {examples}",
    "comprises types such as {examples}",
]

PART_OF_CHILDREN_FORMULATIONS = [
    "contains components such as {examples}",
    "includes structures like {examples}",
    "comprises elements such as {examples}",
    "houses components like {examples}",
    "contains parts such as {examples}",
    "includes examples like {examples}",
]


@dataclass
class AugmentationOptions:
    """Configuration for text augmentation."""
    num_variations: int = 5
    max_relationship_distance: int = 2
    synonym_probability: float = 0.5
    definition_probability: float = 0.3
    go_id_probability: float = 0.2
    # Relationship probabilities (fine-grained control)
    is_a_parent_probability: float = 0.3
    is_a_children_probability: float = 0.3  
    part_of_parent_probability: float = 0.3
    part_of_children_probability: float = 0.3
    # Legacy: overall relationship probability (for backwards compatibility)
    relationship_probability: Optional[float] = None  # If set, overrides individual probabilities
    definition_max_length: Optional[int] = None  # None = no truncation


class GOTextAugmentor:
    """Augments text by replacing hashtag-prefixed terms with GO term variations."""
    
    def __init__(self, client: GOClient):
        """Initialize the augmentor with a GO client.
        
        Args:
            client: GOClient instance for database queries
        """
        self.client = client
    
    def extract_hashtag_terms(self, text: str) -> List[str]:
        """Extract hashtag-prefixed terms from text.
        
        Args:
            text: Input text containing hashtag terms
            
        Returns:
            List of hashtag terms (without the #)
        """
        # Pattern to match hashtags: # followed by word characters, underscores, or hyphens
        pattern = r'#([a-zA-Z_][a-zA-Z0-9_-]*)'
        matches = re.findall(pattern, text)
        
        # Convert underscores back to spaces for GO term lookup
        return [term.replace('_', ' ') for term in matches]
    
    def find_go_terms_for_hashtags(self, hashtag_terms: List[str]) -> Dict[str, Optional[GOTerm]]:
        """Find GO terms for hashtag terms using fuzzy search.
        
        Args:
            hashtag_terms: List of hashtag terms to search for
            
        Returns:
            Dictionary mapping hashtag terms to found GO terms (or None if not found)
        """
        go_terms = {}
        
        for term in hashtag_terms:
            # Search for the term with high confidence threshold
            search_results = self.client.search_terms(term, limit=1, min_score=70.0)
            
            if search_results:
                go_terms[term] = search_results[0].term
            else:
                go_terms[term] = None
                
        return go_terms
    
    def get_relationship_blurb(self, go_term: GOTerm, options: AugmentationOptions) -> Optional[str]:
        """Generate a short blurb about relationships for a GO term.
        
        Args:
            go_term: GO term to get relationships for
            options: Augmentation options containing probabilities and max distance
            
        Returns:
            Short descriptive blurb or None if no relationships found
        """
        try:
            relationships = self.client.get_all_related_terms(go_term.accession, options.max_relationship_distance)
            
            # Determine which probabilities to use
            if options.relationship_probability is not None:
                # Legacy mode: use overall probability for all relationships
                is_a_parent_prob = options.relationship_probability
                is_a_children_prob = options.relationship_probability  
                part_of_parent_prob = options.relationship_probability
                part_of_children_prob = options.relationship_probability
            else:
                # Fine-grained mode: use individual probabilities
                is_a_parent_prob = options.is_a_parent_probability
                is_a_children_prob = options.is_a_children_probability
                part_of_parent_prob = options.part_of_parent_probability
                part_of_children_prob = options.part_of_children_probability
            
            blurbs = []
            
            # IS_A parents (more general terms)
            if relationships["is_a_parents"] and random.random() < is_a_parent_prob:
                parent_names = [rel.term.name for rel in relationships["is_a_parents"][:2]]
                parents_str = parent_names[0] if len(parent_names) == 1 else f"{parent_names[0]} and {parent_names[1]}"
                formulation = random.choice(IS_A_PARENT_FORMULATIONS)
                blurbs.append(formulation.format(parents=parents_str))
            
            # PART_OF parents (what it's part of)
            if relationships["part_of_parents"] and random.random() < part_of_parent_prob:
                parent_names = [rel.term.name for rel in relationships["part_of_parents"][:2]]
                parents_str = parent_names[0] if len(parent_names) == 1 else f"{parent_names[0]} and {parent_names[1]}"
                formulation = random.choice(PART_OF_PARENT_FORMULATIONS)
                blurbs.append(formulation.format(parents=parents_str))
            
            # IS_A children (more specific terms)
            if relationships["is_a_children"] and random.random() < is_a_children_prob:
                # Pick up to 3 random examples
                examples = random.sample(relationships["is_a_children"], min(3, len(relationships["is_a_children"])))
                example_names = []
                for rel in examples:
                    # Use synonym if available, otherwise use the term name
                    if rel.term.synonyms and random.random() < 0.3:  # 30% chance to use synonym
                        example_names.append(random.choice(rel.term.synonyms))
                    else:
                        example_names.append(rel.term.name)
                
                # Format examples list
                if len(example_names) == 1:
                    examples_str = example_names[0]
                elif len(example_names) == 2:
                    examples_str = f"{example_names[0]} and {example_names[1]}"
                else:  # 3 examples
                    examples_str = f"{example_names[0]}, {example_names[1]}, and {example_names[2]}"
                
                formulation = random.choice(IS_A_CHILDREN_FORMULATIONS)
                blurbs.append(formulation.format(examples=examples_str))
            
            # PART_OF children (what's part of it)
            if relationships["part_of_children"] and random.random() < part_of_children_prob:
                # Pick up to 3 random examples
                examples = random.sample(relationships["part_of_children"], min(3, len(relationships["part_of_children"])))
                example_names = []
                for rel in examples:
                    # Use synonym if available, otherwise use the term name
                    if rel.term.synonyms and random.random() < 0.3:  # 30% chance to use synonym
                        example_names.append(random.choice(rel.term.synonyms))
                    else:
                        example_names.append(rel.term.name)
                
                # Format examples list
                if len(example_names) == 1:
                    examples_str = example_names[0]
                elif len(example_names) == 2:
                    examples_str = f"{example_names[0]} and {example_names[1]}"
                else:  # 3 examples
                    examples_str = f"{example_names[0]}, {example_names[1]}, and {example_names[2]}"
                
                formulation = random.choice(PART_OF_CHILDREN_FORMULATIONS)
                blurbs.append(formulation.format(examples=examples_str))
            
            return random.choice(blurbs) if blurbs else None
            
        except Exception:
            return None
    
    def create_term_variation(self, original_term: str, go_term: GOTerm, options: AugmentationOptions) -> str:
        """Create a single variation of a term with potential annotations.
        
        Args:
            original_term: Original hashtag term (with spaces)
            go_term: Corresponding GO term
            options: Augmentation options
            
        Returns:
            Varied term string with potential annotations
        """
        # Start with either original term name or a synonym
        if go_term.synonyms and random.random() < options.synonym_probability:
            base_term = random.choice(go_term.synonyms)
        else:
            base_term = go_term.name
        
        annotations = []
        
        # Add GO ID
        if random.random() < options.go_id_probability:
            annotations.append(go_term.accession)
        
        # Add definition (with optional truncation)
        if go_term.definition and random.random() < options.definition_probability:
            definition = go_term.definition
            if options.definition_max_length and len(definition) > options.definition_max_length:
                definition = definition[:options.definition_max_length-3] + "..."
            annotations.append(definition)
        
        # Add relationship blurb (now handled by individual probabilities within the method)
        blurb = self.get_relationship_blurb(go_term, options)
        if blurb:
            annotations.append(blurb)
        
        # Combine base term with annotations
        if annotations:
            annotation_str = "; ".join(annotations)
            return f"{base_term} ({annotation_str})"
        else:
            return base_term
    
    def augment_text(self, text: str, options: AugmentationOptions) -> List[str]:
        """Generate multiple variations of text with GO term augmentations.
        
        Args:
            text: Input text with hashtag-prefixed GO terms
            options: Augmentation configuration
            
        Returns:
            List of augmented text variations
        """
        # Extract hashtag terms
        hashtag_terms = self.extract_hashtag_terms(text)
        
        if not hashtag_terms:
            return [text] * options.num_variations
        
        # Find GO terms for hashtag terms
        go_term_mapping = self.find_go_terms_for_hashtags(hashtag_terms)
        
        # Filter out terms that weren't found
        valid_mappings = {term: go_term for term, go_term in go_term_mapping.items() 
                         if go_term is not None}
        
        if not valid_mappings:
            return [text] * options.num_variations
        
        variations = []
        
        for _ in range(options.num_variations):
            current_text = text
            
            # Replace each hashtag term with a variation
            for original_term, go_term in valid_mappings.items():
                # Convert term back to hashtag format (spaces to underscores)
                hashtag_pattern = '#' + original_term.replace(' ', '_')
                
                # Create a variation for this term
                variation = self.create_term_variation(original_term, go_term, options)
                
                # Replace the hashtag with the variation
                current_text = current_text.replace(hashtag_pattern, variation)
            
            variations.append(current_text)
        
        return variations
    
    def get_term_info(self, text: str) -> Dict[str, Dict]:
        """Get information about hashtag terms found in text.
        
        Args:
            text: Input text with hashtag terms
            
        Returns:
            Dictionary with term info including match status and GO term details
        """
        hashtag_terms = self.extract_hashtag_terms(text)
        go_term_mapping = self.find_go_terms_for_hashtags(hashtag_terms)
        
        info = {}
        for term, go_term in go_term_mapping.items():
            if go_term:
                info[term] = {
                    "found": True,
                    "go_id": go_term.accession,
                    "name": go_term.name,
                    "synonyms": go_term.synonyms,
                    "definition": go_term.definition[:100] + "..." if len(go_term.definition) > 100 else go_term.definition
                }
            else:
                info[term] = {
                    "found": False,
                    "error": "No matching GO term found"
                }
        
        return info