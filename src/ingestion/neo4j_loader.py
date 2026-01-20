"""
Neo4j Loader with Two-Pass Strategy

Loads SPEED events and CAMEO ontology into Neo4j with:
- Schema creation (constraints, indexes)
- CAMEO ontology loading
- Two-pass event loading:
  Pass 1: Events, Actors, Locations, and relationships
  Pass 2: Event-to-event linkages
- Transaction management and error handling
- Retry logic for resilience
"""

from neo4j import GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable, TransientError
from pathlib import Path
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

from src.domain.events import Event
from src.domain.actors import generate_actor_id
from src.domain.cameo import CAMEOOntology, CAMEOEventType, CAMEOActorType
from src.ingestion.csv_parser import SPEEDCSVParser
from src.ingestion.cameo_parser import CAMEOParser

logger = structlog.get_logger()


class Neo4jLoader:
    """Load SPEED events and CAMEO ontology into Neo4j."""

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j loader.

        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self._connect()

    def _connect(self):
        """Establish connection to Neo4j."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Verify connectivity
            self.driver.verify_connectivity()
            logger.info("neo4j_connected", uri=self.uri)
        except Exception as e:
            logger.error("neo4j_connection_failed", uri=self.uri, error=str(e))
            raise

    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            logger.info("neo4j_connection_closed")

    def __del__(self):
        """Cleanup on deletion."""
        self.close()

    def create_schema(self):
        """Create constraints and indexes."""
        logger.info("creating_schema")

        constraints = [
            # Unique constraints
            "CREATE CONSTRAINT event_id_unique IF NOT EXISTS FOR (e:Event) REQUIRE e.eventId IS UNIQUE",
            "CREATE CONSTRAINT actor_id_unique IF NOT EXISTS FOR (a:Actor) REQUIRE a.actorId IS UNIQUE",
            "CREATE CONSTRAINT eventtype_code_unique IF NOT EXISTS FOR (et:EventType) REQUIRE et.cameoCode IS UNIQUE",
            "CREATE CONSTRAINT location_id_unique IF NOT EXISTS FOR (l:Location) REQUIRE l.locationId IS UNIQUE",
            "CREATE CONSTRAINT cameo_actor_type_unique IF NOT EXISTS FOR (cat:CAMEOActorType) REQUIRE cat.code IS UNIQUE"
        ]

        indexes = [
            # Performance indexes
            "CREATE INDEX event_temporal IF NOT EXISTS FOR (e:Event) ON (e.year, e.month, e.day)",
            "CREATE INDEX event_julian IF NOT EXISTS FOR (e:Event) ON (e.julianStartDate, e.julianEndDate)",
            "CREATE INDEX event_type IF NOT EXISTS FOR (e:Event) ON (e.eventType)",
            "CREATE INDEX actor_cameo IF NOT EXISTS FOR (a:Actor) ON (a.cameoCode)",
            "CREATE INDEX actor_name IF NOT EXISTS FOR (a:Actor) ON (a.name)",
            "CREATE INDEX eventtype_category IF NOT EXISTS FOR (et:EventType) ON (et.category)",
            "CREATE INDEX location_spatial IF NOT EXISTS FOR (l:Location) ON (l.latitude, l.longitude)",
            "CREATE INDEX location_country IF NOT EXISTS FOR (l:Location) ON (l.country)"
        ]

        with self.driver.session() as session:
            # Create constraints
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.debug("constraint_created", query=constraint[:50])
                except Exception as e:
                    logger.warning("constraint_exists", error=str(e)[:100])

            # Create indexes
            for index in indexes:
                try:
                    session.run(index)
                    logger.debug("index_created", query=index[:50])
                except Exception as e:
                    logger.warning("index_exists", error=str(e)[:100])

        logger.info("schema_created")

    def load_cameo_ontology(self, cameo_dir: Path):
        """
        Load CAMEO reference data into Neo4j.

        Args:
            cameo_dir: Directory containing CAMEO files
        """
        logger.info("loading_cameo_ontology", dir=str(cameo_dir))

        # Parse CAMEO files
        parser = CAMEOParser()
        ontology = parser.parse_all(cameo_dir)

        # Load into Neo4j
        self._load_event_types(ontology.event_types, ontology.build_event_hierarchy())
        self._load_actor_types(ontology.actor_types)

        logger.info(
            "cameo_ontology_loaded",
            event_types=len(ontology.event_types),
            actor_types=len(ontology.actor_types)
        )

    def _load_event_types(self, event_types: List[CAMEOEventType], hierarchy: Dict[str, List[str]]):
        """Load CAMEO event type hierarchy."""
        logger.info("loading_event_types", count=len(event_types))

        with self.driver.session() as session:
            # Create event type nodes
            for et in event_types:
                session.run("""
                    MERGE (et:EventType {cameoCode: $code})
                    SET et.label = $label,
                        et.level = $level,
                        et.category = $category,
                        et.isCooperation = $is_coop,
                        et.isConflict = $is_conflict,
                        et.isMaterial = $is_material,
                        et.isVerbal = $is_verbal
                """,
                    code=et.code,
                    label=et.label,
                    level=et.level,
                    category=et.root_category,
                    is_coop=et.is_cooperation,
                    is_conflict=et.is_conflict,
                    is_material=et.is_material,
                    is_verbal=et.is_verbal
                )

            # Create hierarchy relationships
            for parent_code, child_codes in hierarchy.items():
                for child_code in child_codes:
                    session.run("""
                        MATCH (parent:EventType {cameoCode: $parent})
                        MATCH (child:EventType {cameoCode: $child})
                        MERGE (child)-[:PARENT_TYPE]->(parent)
                    """, parent=parent_code, child=child_code)

        logger.info("event_types_loaded", count=len(event_types))

    def _load_actor_types(self, actor_types: List[CAMEOActorType]):
        """Load CAMEO actor types."""
        logger.info("loading_actor_types", count=len(actor_types))

        with self.driver.session() as session:
            for actor in actor_types:
                session.run("""
                    MERGE (at:CAMEOActorType {code: $code})
                    SET at.name = $name,
                        at.description = $description,
                        at.baseCountry = $base_country,
                        at.actorType = $actor_type,
                        at.isInternationalOrg = $is_intl_org
                """,
                    code=actor.code,
                    name=actor.name,
                    description=actor.description,
                    base_country=actor.base_country,
                    actor_type=actor.actor_type,
                    is_intl_org=actor.is_international_org
                )

        logger.info("actor_types_loaded", count=len(actor_types))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def load_events(self, csv_path: Path, batch_size: int = 500):
        """
        Load SPEED events with two-pass strategy.

        Pass 1: Create all events, actors, locations
        Pass 2: Create event linkages

        Args:
            csv_path: Path to SPEED CSV file
            batch_size: Number of events per batch
        """
        logger.info("loading_events", csv_path=str(csv_path), batch_size=batch_size)

        parser = SPEEDCSVParser(csv_path)

        # Pass 1: Load events
        batch = []
        total_loaded = 0

        for event in parser.parse():
            batch.append(event)

            if len(batch) >= batch_size:
                self._load_event_batch(batch)
                total_loaded += len(batch)
                logger.info("batch_loaded", count=total_loaded)
                batch = []

        # Load remaining
        if batch:
            self._load_event_batch(batch)
            total_loaded += len(batch)

        logger.info("events_loaded_pass1", total=total_loaded, errors=len(parser.errors))

        # Pass 2: Create event linkages
        self._create_event_links()

        logger.info(
            "event_loading_complete",
            total_events=total_loaded,
            errors=len(parser.errors)
        )

    def _load_event_batch(self, events: List[Event]):
        """
        Load a batch of events with actors and locations.

        Args:
            events: List of Event objects
        """
        with self.driver.session() as session:
            with session.begin_transaction() as tx:
                for event in events:
                    try:
                        self._create_event_node(tx, event)
                        self._create_actor_relationships(tx, event)
                        self._create_location_relationship(tx, event)
                        self._link_event_type(tx, event)
                    except Exception as e:
                        logger.error(
                            "event_load_failed",
                            event_id=event.event_id,
                            error=str(e)
                        )
                        # Continue with other events

                tx.commit()

    def _create_event_node(self, tx, event: Event):
        """Create Event node."""
        import json

        # Convert properties dict to JSON string for Neo4j storage
        properties_json = json.dumps(event.properties) if event.properties else None

        tx.run("""
            CREATE (e:Event {
                eventId: $event_id,
                year: $year,
                month: $month,
                day: $day,
                dateType: $date_type,
                julianStartDate: $julian_start,
                julianEndDate: $julian_end,
                daySpan: $day_span,
                eventType: $event_type,
                peType: $pe_type,
                atkType: $atk_type,
                dsaType: $dsa_type,
                newsSource: $news_source,
                articleId: $article_id,
                isQuasiEvent: $is_quasi,
                isStateAction: $is_state_action,
                isCoup: $is_coup,
                isCoupFailed: $is_coup_failed,
                isLinked: $is_linked,
                linkType: $link_type,
                isPosthoc: $is_posthoc,
                propertiesJson: $properties_json
            })
        """,
            event_id=event.event_id,
            year=event.temporal.year if event.temporal else None,
            month=event.temporal.month if event.temporal else None,
            day=event.temporal.day if event.temporal else None,
            date_type=event.temporal.date_type if event.temporal else None,
            julian_start=event.temporal.julian_start_date if event.temporal else None,
            julian_end=event.temporal.julian_end_date if event.temporal else None,
            day_span=event.temporal.day_span if event.temporal else None,
            event_type=event.event_type,
            pe_type=event.pe_type,
            atk_type=event.atk_type,
            dsa_type=event.dsa_type,
            news_source=event.news_source,
            article_id=event.article_id,
            is_quasi=event.is_quasi_event,
            is_state_action=event.is_state_action,
            is_coup=event.is_coup,
            is_coup_failed=event.is_coup_failed,
            is_linked=event.is_linked,
            link_type=event.link_type,
            is_posthoc=event.is_posthoc,
            properties_json=properties_json
        )

    def _create_actor_relationships(self, tx, event: Event):
        """Create actor nodes and relationships."""
        # Initiator
        if event.initiator and event.initiator.primary_name:
            actor_id = generate_actor_id(event.initiator.primary_name)
            tx.run("""
                MERGE (a:Actor {actorId: $actor_id})
                ON CREATE SET
                    a.name = $name,
                    a.cameoCode = $cameo_code,
                    a.isGovernment = $is_gov
                WITH a
                MATCH (e:Event {eventId: $event_id})
                MERGE (e)-[r:INITIATED_BY]->(a)
                SET r.actorType = $actor_type,
                    r.governmentType = $gov_type,
                    r.governmentLevel = $gov_level,
                    r.ambiguity = $ambiguity,
                    r.numParticipants = $num_participants,
                    r.numArmed = $num_armed
            """,
                actor_id=actor_id,
                name=event.initiator.primary_name,
                cameo_code=event.initiator.identity_group,
                is_gov=event.initiator.is_government,
                event_id=event.event_id,
                actor_type=event.initiator.actor_type,
                gov_type=event.initiator.government_type,
                gov_level=event.initiator.government_level,
                ambiguity=event.initiator.ambiguity,
                num_participants=event.initiator.num_participants,
                num_armed=event.initiator.num_armed
            )

        # Target
        if event.target and event.target.primary_name:
            actor_id = generate_actor_id(event.target.primary_name)
            tx.run("""
                MERGE (a:Actor {actorId: $actor_id})
                ON CREATE SET
                    a.name = $name,
                    a.cameoCode = $cameo_code,
                    a.isGovernment = $is_gov
                WITH a
                MATCH (e:Event {eventId: $event_id})
                MERGE (e)-[r:TARGETED]->(a)
                SET r.actorType = $actor_type,
                    r.governmentType = $gov_type,
                    r.governmentLevel = $gov_level,
                    r.isHuman = $is_human
            """,
                actor_id=actor_id,
                name=event.target.primary_name,
                cameo_code=event.target.identity_group,
                is_gov=event.target.is_government,
                event_id=event.event_id,
                actor_type=event.target.actor_type,
                gov_type=event.target.government_type,
                gov_level=event.target.government_level,
                is_human=event.target.is_human
            )

        # Victim
        if event.victim and event.victim.primary_name:
            actor_id = generate_actor_id(event.victim.primary_name)
            tx.run("""
                MERGE (a:Actor {actorId: $actor_id})
                ON CREATE SET
                    a.name = $name,
                    a.cameoCode = $cameo_code,
                    a.isGovernment = $is_gov
                WITH a
                MATCH (e:Event {eventId: $event_id})
                MERGE (e)-[r:VICTIMIZED]->(a)
                SET r.actorType = $actor_type,
                    r.governmentType = $gov_type,
                    r.governmentLevel = $gov_level,
                    r.isHuman = $is_human
            """,
                actor_id=actor_id,
                name=event.victim.primary_name,
                cameo_code=event.victim.identity_group,
                is_gov=event.victim.is_government,
                event_id=event.event_id,
                actor_type=event.victim.actor_type,
                gov_type=event.victim.government_type,
                gov_level=event.victim.government_level,
                is_human=event.victim.is_human
            )

    def _create_location_relationship(self, tx, event: Event):
        """Create location node and relationship."""
        if event.location and (event.location.name or event.location.country):
            location_id = self._generate_location_id(
                event.location.name or event.location.country,
                event.location.latitude,
                event.location.longitude
            )

            tx.run("""
                MERGE (l:Location {locationId: $location_id})
                ON CREATE SET
                    l.name = $name,
                    l.country = $country,
                    l.latitude = $lat,
                    l.longitude = $lon,
                    l.locationType = $loc_type,
                    l.region = $region
                WITH l
                MATCH (e:Event {eventId: $event_id})
                MERGE (e)-[:OCCURRED_AT]->(l)
            """,
                location_id=location_id,
                name=event.location.name,
                country=event.location.country,
                lat=event.location.latitude,
                lon=event.location.longitude,
                loc_type=event.location.location_type,
                region=event.location.region,
                event_id=event.event_id
            )

    def _link_event_type(self, tx, event: Event):
        """Link event to CAMEO event type."""
        if event.event_type:
            # Try to link to CAMEO event type
            tx.run("""
                MATCH (e:Event {eventId: $event_id})
                OPTIONAL MATCH (et:EventType {cameoCode: $cameo_code})
                FOREACH (_ IN CASE WHEN et IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (e)-[:OF_TYPE]->(et)
                )
            """, event_id=event.event_id, cameo_code=str(event.event_type))

    def _create_event_links(self):
        """Second pass: Create event-to-event linkages."""
        logger.info("creating_event_links")

        with self.driver.session() as session:
            # Find all events with linkages
            result = session.run("""
                MATCH (e:Event)
                WHERE e.isLinked = true
                RETURN e.eventId as event_id, e.properties as props
            """)

            link_count = 0
            for record in result:
                props = record["props"] or {}

                # Link FROM_EID
                from_eid = props.get('FROM_EID')
                if from_eid:
                    session.run("""
                        MATCH (e1:Event {eventId: $from_eid})
                        MATCH (e2:Event {eventId: $to_eid})
                        MERGE (e1)-[r:LINKED_TO]->(e2)
                        SET r.direction = 'from'
                    """, from_eid=from_eid, to_eid=record["event_id"])
                    link_count += 1

                # Link TO_EID
                to_eid = props.get('TO_EID')
                if to_eid:
                    session.run("""
                        MATCH (e1:Event {eventId: $from_eid})
                        MATCH (e2:Event {eventId: $to_eid})
                        MERGE (e1)-[r:LINKED_TO]->(e2)
                        SET r.direction = 'to'
                    """, from_eid=record["event_id"], to_eid=to_eid)
                    link_count += 1

            logger.info("event_links_created", count=link_count)

    def _generate_location_id(self, name: str, lat: Optional[float], lon: Optional[float]) -> str:
        """Generate stable location ID."""
        import hashlib
        key = f"{name}_{lat}_{lon}".lower()
        return f"LOC_{hashlib.md5(key.encode()).hexdigest()[:12].upper()}"

    def get_stats(self) -> Dict[str, int]:
        """
        Get database statistics.

        Returns:
            Dictionary with node and relationship counts
        """
        with self.driver.session() as session:
            # Node counts
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(n) as count
            """)
            node_counts = {record["label"]: record["count"] for record in result}

            # Relationship counts
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
            """)
            rel_counts = {record["type"]: record["count"] for record in result}

            return {
                "nodes": node_counts,
                "relationships": rel_counts
            }
