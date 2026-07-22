import logging
from neo4j import GraphDatabase, Driver
from app.config import settings

logger = logging.getLogger("garc.db")

class Neo4jClient:
    def __init__(self):
        self.driver: Driver | None = None
        self.mock_mode: bool = False
        self._mock_nodes = []
        self._mock_edges = []
        self._init_connection()

    def _init_connection(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            self.driver.verify_connectivity()
            logger.info("Connected successfully to Neo4j database.")
        except Exception as e:
            logger.warning(f"Could not connect to Neo4j at {settings.NEO4J_URI} ({e}). Falling back to In-Memory Mock Graph mode.")
            self.driver = None
            self.mock_mode = True

    def close(self):
        if self.driver:
            self.driver.close()

    def query(self, cypher: str, parameters: dict = None):
        if self.mock_mode or not self.driver:
            logger.info(f"[MOCK GRAPH QUERY]: {cypher} | params: {parameters}")
            return []
        
        with self.driver.session() as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    def execute_write(self, cypher: str, parameters: dict = None):
        if self.mock_mode or not self.driver:
            logger.info(f"[MOCK GRAPH WRITE]: {cypher} | params: {parameters}")
            return {"status": "mock_success"}

        with self.driver.session() as session:
            result = session.execute_write(lambda tx: tx.run(cypher, parameters or {}).data())
            return result

neo4j_client = Neo4jClient()
