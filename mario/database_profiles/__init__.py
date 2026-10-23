"""Database-specific metadata shared by parsers, GHG calculations and lookups."""
from mario.database_profiles.registry import get_database_profile

__all__ = ["get_database_profile"]
