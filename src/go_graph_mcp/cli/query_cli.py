"""Command line interface for querying GO terms."""

import sys
from pathlib import Path

import click

from go_graph_mcp.client import GOClient, GOTextAugmentor, AugmentationOptions, TaxonomyFilterOptions


@click.group()
def cli():
    """Query GO terms from KuzuDB with fuzzy matching."""
    pass


@cli.command()
@click.option(
    "--database",
    "-d",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="Path to the KuzuDB database",
)
@click.argument("go_id")
def get_term(database, go_id):
    """Get a GO term by its exact ID."""
    try:
        with GOClient(database) as client:
            term = client.get_term_by_id(go_id)
            if term:
                click.echo(f"ID: {term.accession}")
                click.echo(f"Name: {term.name}")
                click.echo(f"Namespace: {term.namespace}")
                click.echo(f"Definition: {term.definition}")
                if term.comment:
                    click.echo(f"Comment: {term.comment}")
                if term.synonyms:
                    click.echo(f"Synonyms: {', '.join(term.synonyms)}")
            else:
                click.echo(f"Term {go_id} not found.")
                sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--database",
    "-d",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="Path to the KuzuDB database",
)
@click.option(
    "--limit",
    "-l",
    default=10,
    type=int,
    help="Maximum number of results (default: 10)",
)
@click.option(
    "--min-score",
    "-s",
    default=30.0,
    type=float,
    help="Minimum relevance score 0-100 (default: 30.0)",
)
@click.option(
    "--include-taxa",
    multiple=True,
    help="Include only terms for these taxa (e.g., 'plants', 'mammals'). Can be used multiple times.",
)
@click.option(
    "--exclude-taxa", 
    multiple=True,
    help="Exclude terms for these taxa (e.g., 'plants', 'bacteria'). Can be used multiple times.",
)
@click.argument("query")
def search(database, limit, min_score, include_taxa, exclude_taxa, query):
    """Search for GO terms using fuzzy matching."""
    try:
        # Create taxonomy filter if needed
        taxonomy_filter = None
        if include_taxa or exclude_taxa:
            taxonomy_filter = TaxonomyFilterOptions(
                include_taxa=list(include_taxa),
                exclude_taxa=list(exclude_taxa)
            )
        
        with GOClient(database) as client:
            results = client.search_terms(query, limit=limit, min_score=min_score, 
                                        taxonomy_filter=taxonomy_filter)
            
            if not results:
                click.echo(f"No terms found matching '{query}'")
                return
            
            click.echo(f"Found {len(results)} results for '{query}':")
            click.echo()
            
            for i, result in enumerate(results, 1):
                term = result.term
                click.echo(f"{i}. {term.accession} - {term.name}")
                click.echo(f"   Score: {result.score:.1f} (matched via {result.match_type}: '{result.matched_text}')")
                if term.definition:
                    # Truncate long definitions
                    definition = term.definition[:100] + "..." if len(term.definition) > 100 else term.definition
                    click.echo(f"   Definition: {definition}")
                click.echo()
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--database",
    "-d",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="Path to the KuzuDB database",
)
@click.option(
    "--max-distance",
    "-m",
    default=3,
    type=int,
    help="Maximum relationship distance (default: 3)",
)
@click.argument("go_id")
def relationships(database, max_distance, go_id):
    """Show all relationships for a GO term."""
    try:
        with GOClient(database) as client:
            # First verify the term exists
            term = client.get_term_by_id(go_id)
            if not term:
                click.echo(f"Term {go_id} not found.")
                sys.exit(1)
            
            click.echo(f"Relationships for {go_id} - {term.name}")
            click.echo("=" * 60)
            
            related = client.get_all_related_terms(go_id, max_distance)
            
            # IS_A Parents
            if related["is_a_parents"]:
                click.echo(f"\nIS_A Parents ({len(related['is_a_parents'])}):")
                for rel in related["is_a_parents"]:
                    click.echo(f"  Distance {rel.distance}: {rel.term.accession} - {rel.term.name}")
            
            # IS_A Children
            if related["is_a_children"]:
                click.echo(f"\nIS_A Children ({len(related['is_a_children'])}):")
                for rel in related["is_a_children"]:
                    click.echo(f"  Distance {rel.distance}: {rel.term.accession} - {rel.term.name}")
            
            # PART_OF Parents
            if related["part_of_parents"]:
                click.echo(f"\nPART_OF Parents ({len(related['part_of_parents'])}):")
                for rel in related["part_of_parents"]:
                    click.echo(f"  Distance {rel.distance}: {rel.term.accession} - {rel.term.name}")
            
            # PART_OF Children
            if related["part_of_children"]:
                click.echo(f"\nPART_OF Children ({len(related['part_of_children'])}):")
                for rel in related["part_of_children"]:
                    click.echo(f"  Distance {rel.distance}: {rel.term.accession} - {rel.term.name}")
            
            if not any(related.values()):
                click.echo("\nNo relationships found.")
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--database",
    "-d",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="Path to the KuzuDB database",
)
def stats(database):
    """Show database statistics."""
    try:
        with GOClient(database) as client:
            stats = client.get_database_stats()
            
            click.echo("Database Statistics:")
            click.echo("=" * 30)
            click.echo(f"GO Terms: {stats.get('go_terms', 0):,}")
            click.echo(f"Synonyms: {stats.get('synonyms', 0):,}")
            click.echo(f"IS_A Relationships: {stats.get('is_a_relationships', 0):,}")
            click.echo(f"PART_OF Relationships: {stats.get('part_of_relationships', 0):,}")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--database",
    "-d",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="Path to the KuzuDB database",
)
@click.argument("text")
def analyze_hashtags(database, text):
    """Analyze hashtag terms in text and show GO term matches."""
    try:
        with GOClient(database) as client:
            augmentor = GOTextAugmentor(client)
            term_info = augmentor.get_term_info(text)
            
            if not term_info:
                click.echo("No hashtag terms found in text.")
                return
            
            click.echo("Hashtag Term Analysis:")
            click.echo("=" * 40)
            
            for term, info in term_info.items():
                click.echo(f"\n#{term.replace(' ', '_')}")
                if info["found"]:
                    click.echo(f"  ✓ Found: {info['go_id']} - {info['name']}")
                    if info['synonyms']:
                        click.echo(f"  Synonyms: {', '.join(info['synonyms'])}")
                    click.echo(f"  Definition: {info['definition']}")
                else:
                    click.echo(f"  ✗ {info['error']}")
                    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--database",
    "-d",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="Path to the KuzuDB database",
)
@click.option(
    "--num-variations",
    "-n",
    default=5,
    type=int,
    help="Number of text variations to generate (default: 5)",
)
@click.option(
    "--max-distance",
    "-m",
    default=2,
    type=int,
    help="Maximum relationship distance for blurbs (default: 2)",
)
@click.option(
    "--synonym-prob",
    default=0.5,
    type=float,
    help="Probability of using synonyms (0.0-1.0, default: 0.5)",
)
@click.option(
    "--definition-prob",
    default=0.3,
    type=float,
    help="Probability of including definitions (0.0-1.0, default: 0.3)",
)
@click.option(
    "--go-id-prob",
    default=0.2,
    type=float,
    help="Probability of including GO IDs (0.0-1.0, default: 0.2)",
)
@click.option(
    "--relationship-prob",
    default=None,
    type=float,
    help="Legacy: overall probability for all relationships (0.0-1.0). If set, overrides individual probabilities.",
)
@click.option(
    "--is-a-parent-prob",
    default=0.3,
    type=float,
    help="Probability of including IS_A parent relationships (0.0-1.0, default: 0.3)",
)
@click.option(
    "--is-a-children-prob",
    default=0.3,
    type=float,
    help="Probability of including IS_A children examples (0.0-1.0, default: 0.3)",
)
@click.option(
    "--part-of-parent-prob",
    default=0.3,
    type=float,
    help="Probability of including PART_OF parent relationships (0.0-1.0, default: 0.3)",
)
@click.option(
    "--part-of-children-prob",
    default=0.3,
    type=float,
    help="Probability of including PART_OF children examples (0.0-1.0, default: 0.3)",
)
@click.option(
    "--definition-max-length",
    type=int,
    help="Maximum length for definitions (default: no truncation)",
)
@click.argument("text")
def augment_text(database, num_variations, max_distance, synonym_prob, 
                definition_prob, go_id_prob, relationship_prob, is_a_parent_prob,
                is_a_children_prob, part_of_parent_prob, part_of_children_prob, 
                definition_max_length, text):
    """Generate variations of text by augmenting hashtag GO terms."""
    try:
        with GOClient(database) as client:
            augmentor = GOTextAugmentor(client)
            
            options = AugmentationOptions(
                num_variations=num_variations,
                max_relationship_distance=max_distance,
                synonym_probability=synonym_prob,
                definition_probability=definition_prob,
                go_id_probability=go_id_prob,
                relationship_probability=relationship_prob,
                is_a_parent_probability=is_a_parent_prob,
                is_a_children_probability=is_a_children_prob,
                part_of_parent_probability=part_of_parent_prob,
                part_of_children_probability=part_of_children_prob,
                definition_max_length=definition_max_length
            )
            
            variations = augmentor.augment_text(text, options)
            
            click.echo(f"Generated {len(variations)} variations:")
            click.echo("=" * 50)
            
            for i, variation in enumerate(variations, 1):
                click.echo(f"\n{i}. {variation}")
                    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()