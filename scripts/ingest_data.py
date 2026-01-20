#!/usr/bin/env python3
"""
SPEED Data Ingestion Script

Loads CAMEO ontology and SPEED events into Neo4j.

Usage:
    python scripts/ingest_data.py [--batch-size 500] [--validate-only]
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import get_config
from src.utils.logging import setup_logging, get_logger
from src.ingestion.schema_validator import SchemaValidator
from src.ingestion.neo4j_loader import Neo4jLoader


def main():
    """Main ingestion workflow."""
    parser = argparse.ArgumentParser(description="Ingest SPEED data into Neo4j")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of events per batch (default: 500)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate schema, don't load data"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip schema validation"
    )
    parser.add_argument(
        "--skip-cameo",
        action="store_true",
        help="Skip CAMEO ontology loading"
    )

    args = parser.parse_args()

    # Load configuration
    config = get_config()

    # Setup logging
    logger = setup_logging(log_level=config.LOG_LEVEL, logs_dir=config.LOGS_DIR)

    logger.info("starting_data_ingestion", config=str(config))

    # Validate data files exist
    all_exist, missing = config.validate_data_files()
    if not all_exist:
        logger.error("missing_data_files", missing=missing)
        print("\n❌ Missing required data files:")
        for file in missing:
            print(f"  - {file}")
        print("\nPlease ensure all data files are present before running ingestion.")
        sys.exit(1)

    # Validate schema
    if not args.skip_validation:
        logger.info("validating_schema")
        validator = SchemaValidator()
        is_valid = validator.validate_and_report(config.speed_csv, sample_size=1000)

        if not is_valid:
            logger.error("schema_validation_failed")
            sys.exit(1)

        if args.validate_only:
            logger.info("validation_complete_exiting")
            sys.exit(0)

    # Initialize Neo4j loader
    try:
        loader = Neo4jLoader(
            uri=config.NEO4J_URI,
            user=config.NEO4J_USER,
            password=config.NEO4J_PASSWORD
        )
    except Exception as e:
        logger.error("neo4j_connection_failed", error=str(e))
        print(f"\n❌ Failed to connect to Neo4j: {e}")
        print(f"\nCheck that Neo4j is running at {config.NEO4J_URI}")
        sys.exit(1)

    try:
        # Create schema
        logger.info("creating_schema")
        loader.create_schema()
        print("\n✅ Schema created (constraints and indexes)")

        # Load CAMEO ontology
        if not args.skip_cameo:
            logger.info("loading_cameo_ontology")
            loader.load_cameo_ontology(config.cameo_dir)
            print("✅ CAMEO ontology loaded")

        # Load SPEED events
        logger.info("loading_events", batch_size=args.batch_size)
        print(f"\n📊 Loading SPEED events (batch size: {args.batch_size})...")
        print("This may take 5-10 minutes for the full dataset...\n")

        loader.load_events(config.speed_csv, batch_size=args.batch_size)

        # Get statistics
        stats = loader.get_stats()
        logger.info("ingestion_complete", stats=stats)

        # Print summary
        print("\n" + "=" * 60)
        print("✅ INGESTION COMPLETE")
        print("=" * 60)
        print("\nDatabase Statistics:")
        print("\nNodes:")
        for label, count in stats.get("nodes", {}).items():
            print(f"  {label}: {count:,}")

        print("\nRelationships:")
        for rel_type, count in stats.get("relationships", {}).items():
            print(f"  {rel_type}: {count:,}")

        print("\n" + "=" * 60)
        print("\nNext steps:")
        print("1. Access Neo4j Browser: http://localhost:7474")
        print("2. Run sample Cypher query:")
        print("   MATCH (e:Event)-[:INITIATED_BY]->(a:Actor)")
        print("   RETURN e.eventId, e.year, a.name LIMIT 10")
        print("=" * 60 + "\n")

    except KeyboardInterrupt:
        logger.warning("ingestion_interrupted")
        print("\n\n⚠️  Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("ingestion_failed", error=str(e), exc_info=True)
        print(f"\n❌ Ingestion failed: {e}")
        sys.exit(1)
    finally:
        loader.close()


if __name__ == "__main__":
    main()
