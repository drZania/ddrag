"""SQLAlchemy declarative base and model metadata."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for DDRAG database models."""