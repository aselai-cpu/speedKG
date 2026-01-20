"""
Integration tests for Neo4j loader

These tests require a running Neo4j instance.
"""

import pytest
from pathlib import Path
from neo4j import GraphDatabase
from src.ingestion.neo4j_loader import Neo4jLoader
from src.utils.config import get_config


class TestNeo4jLoaderIntegration:
    """Integration tests for Neo4j loader."""

    @pytest.fixture
    def config(self):
        """Get configuration."""
        return get_config()

    @pytest.fixture
    def loader(self, config):
        """Create loader instance."""
        try:
            loader = Neo4jLoader(
                uri=config.NEO4J_URI,
                user=config.NEO4J_USER,
                password=config.NEO4J_PASSWORD
            )
            yield loader
            loader.close()
        except Exception as e:
            pytest.skip(f"Neo4j not available: {e}")

    @pytest.fixture(autouse=True)
    def cleanup_test_data(self, loader):
        """Clean up test data before and after tests."""
        # Cleanup before test
        with loader.driver.session() as session:
            session.run("MATCH (n:TestEvent) DETACH DELETE n")
            session.run("MATCH (n:TestActor) DETACH DELETE n")

        yield

        # Cleanup after test
        with loader.driver.session() as session:
            session.run("MATCH (n:TestEvent) DETACH DELETE n")
            session.run("MATCH (n:TestActor) DETACH DELETE n")

    def test_connection(self, loader):
        """Test Neo4j connection."""
        assert loader.driver is not None
        loader.driver.verify_connectivity()

    def test_create_schema(self, loader):
        """Test schema creation."""
        loader.create_schema()

        # Verify constraints exist
        with loader.driver.session() as session:
            result = session.run("SHOW CONSTRAINTS")
            constraints = [record["name"] for record in result]

            assert any("event_id" in c.lower() for c in constraints)
            assert any("actor_id" in c.lower() for c in constraints)

    @pytest.mark.skipif(
        not Path("data/cameo").exists(),
        reason="CAMEO data not found"
    )
    def test_load_cameo_ontology(self, loader, config):
        """Test CAMEO ontology loading."""
        loader.load_cameo_ontology(config.cameo_dir)

        # Verify event types were loaded
        with loader.driver.session() as session:
            result = session.run("MATCH (et:EventType) RETURN count(et) as count")
            count = result.single()["count"]
            assert count > 0

            # Check for specific event types
            result = session.run("""
                MATCH (et:EventType {cameoCode: '01'})
                RETURN et.label as label
            """)
            record = result.single()
            assert record is not None
            assert "statement" in record["label"].lower()

    def test_create_event_node(self, loader):
        """Test event node creation."""
        from src.domain.events import Event, TemporalInfo

        temporal = TemporalInfo(year=2000, month=1, day=1)
        event = Event(event_id="TEST001", temporal=temporal, event_type=1)

        with loader.driver.session() as session:
            with session.begin_transaction() as tx:
                # Use test label
                tx.run("""
                    CREATE (e:TestEvent {
                        eventId: $event_id,
                        year: $year,
                        eventType: $event_type
                    })
                """,
                    event_id=event.event_id,
                    year=event.temporal.year,
                    event_type=event.event_type
                )
                tx.commit()

            # Verify
            result = session.run("""
                MATCH (e:TestEvent {eventId: 'TEST001'})
                RETURN e.year as year
            """)
            record = result.single()
            assert record["year"] == 2000

    def test_create_actor_relationship(self, loader):
        """Test actor relationship creation."""
        with loader.driver.session() as session:
            # Create test event and actor
            session.run("""
                CREATE (e:TestEvent {eventId: 'TEST002'})
                CREATE (a:TestActor {actorId: 'ACTOR_TEST', name: 'Test Actor'})
                CREATE (e)-[:INITIATED_BY]->(a)
            """)

            # Verify relationship
            result = session.run("""
                MATCH (e:TestEvent {eventId: 'TEST002'})-[:INITIATED_BY]->(a:TestActor)
                RETURN a.name as name
            """)
            record = result.single()
            assert record["name"] == "Test Actor"

    def test_get_stats(self, loader):
        """Test statistics retrieval."""
        stats = loader.get_stats()

        assert "nodes" in stats
        assert "relationships" in stats
        assert isinstance(stats["nodes"], dict)
        assert isinstance(stats["relationships"], dict)


# Full integration test (requires full dataset)
@pytest.mark.integration
@pytest.mark.skipif(
    not Path("data/ssp_public.csv").exists(),
    reason="SPEED CSV not found"
)
class TestFullIngestion:
    """Full ingestion integration test."""

    def test_full_ingestion_sample(self, tmp_path):
        """Test ingestion of first 100 events."""
        import csv
        from src.utils.config import Config

        # Create sample CSV with first 100 rows
        source_csv = Path("data/ssp_public.csv")
        sample_csv = tmp_path / "sample.csv"

        with open(source_csv, 'r') as src:
            reader = csv.reader(src)
            with open(sample_csv, 'w', newline='') as dst:
                writer = csv.writer(dst)
                for i, row in enumerate(reader):
                    writer.writerow(row)
                    if i >= 100:  # Header + 100 rows
                        break

        # Load sample
        config = get_config()
        loader = Neo4jLoader(
            uri=config.NEO4J_URI,
            user=config.NEO4J_USER,
            password=config.NEO4J_PASSWORD
        )

        try:
            loader.create_schema()
            loader.load_events(sample_csv, batch_size=50)

            stats = loader.get_stats()
            assert stats["nodes"].get("Event", 0) > 0

        finally:
            # Cleanup
            with loader.driver.session() as session:
                # Don't delete all data in integration test
                pass
            loader.close()
