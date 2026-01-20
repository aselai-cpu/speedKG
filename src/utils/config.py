"""
Configuration Management

Loads configuration from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


@dataclass
class Config:
    """Application configuration from environment variables."""

    # Neo4j Configuration
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")

    # Anthropic API
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

    # Application Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_SUBGRAPH_NODES: int = int(os.getenv("MAX_SUBGRAPH_NODES", "500"))
    QUERY_TIMEOUT_SECONDS: int = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))

    # Ingestion Settings
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "500"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))

    # Paths
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "data"))
    LOGS_DIR: Path = Path(os.getenv("LOGS_DIR", "logs"))
    EVALS_DIR: Path = Path(os.getenv("EVALS_DIR", "evals"))

    def __post_init__(self):
        """Validate configuration and create directories."""
        # Ensure directories exist
        self.LOGS_DIR.mkdir(exist_ok=True)
        self.EVALS_DIR.mkdir(exist_ok=True)

        # Validate Neo4j URI format
        if not self.NEO4J_URI.startswith(("bolt://", "neo4j://")):
            raise ValueError(f"Invalid Neo4j URI: {self.NEO4J_URI}")

        # Validate Anthropic API key is set (warn if empty)
        if not self.ANTHROPIC_API_KEY:
            import warnings
            warnings.warn(
                "ANTHROPIC_API_KEY not set. LLM features will not work.",
                UserWarning
            )

    @property
    def cameo_dir(self) -> Path:
        """Get CAMEO data directory."""
        return self.DATA_DIR / "cameo"

    @property
    def speed_csv(self) -> Path:
        """Get SPEED CSV file path."""
        return self.DATA_DIR / "ssp_public.csv"

    @property
    def speed_codebook(self) -> Path:
        """Get SPEED codebook path."""
        return self.DATA_DIR / "SPEED-Codebook.xls"

    def validate_data_files(self) -> tuple[bool, list[str]]:
        """
        Validate that required data files exist.

        Returns:
            Tuple of (all_exist, missing_files)
        """
        required_files = [
            self.speed_csv,
            self.cameo_dir / "Levant.080629.actors",
            self.cameo_dir / "CAMEO.080612.verbs",
            self.cameo_dir / "CAMEO.09b5.options"
        ]

        missing = [str(f) for f in required_files if not f.exists()]

        return (len(missing) == 0, missing)

    def __repr__(self) -> str:
        """String representation (hide sensitive values)."""
        return (
            f"Config(\n"
            f"  NEO4J_URI={self.NEO4J_URI},\n"
            f"  NEO4J_USER={self.NEO4J_USER},\n"
            f"  CLAUDE_MODEL={self.CLAUDE_MODEL},\n"
            f"  LOG_LEVEL={self.LOG_LEVEL},\n"
            f"  DATA_DIR={self.DATA_DIR}\n"
            f")"
        )


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """
    Get global config instance (singleton).

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """
    Force reload configuration from environment.

    Returns:
        New Config instance
    """
    global _config
    load_dotenv(override=True)
    _config = Config()
    return _config
