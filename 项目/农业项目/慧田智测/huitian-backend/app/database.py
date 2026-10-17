from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_database() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_schema()


def _migrate_sqlite_schema() -> None:
    """Add columns introduced after the initial SQLite delivery, without data loss."""
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as connection:
        device_columns = {
            column["name"] for column in inspect(connection).get_columns("devices")
        }
        if "actuator_state" not in device_columns:
            connection.exec_driver_sql(
                "ALTER TABLE devices ADD COLUMN actuator_state "
                "VARCHAR(20) NOT NULL DEFAULT 'unknown'"
            )
        if "state_updated_at" not in device_columns:
            connection.exec_driver_sql(
                "ALTER TABLE devices ADD COLUMN state_updated_at DATETIME"
            )
        if "camera_model" not in device_columns:
            connection.exec_driver_sql(
                "ALTER TABLE devices ADD COLUMN camera_model VARCHAR(100)"
            )
        if "stream_url" not in device_columns:
            connection.exec_driver_sql(
                "ALTER TABLE devices ADD COLUMN stream_url VARCHAR(500)"
            )
        if "capabilities_json" not in device_columns:
            connection.exec_driver_sql(
                "ALTER TABLE devices ADD COLUMN capabilities_json JSON NOT NULL DEFAULT '[]'"
            )
        if "metadata_json" not in device_columns:
            connection.exec_driver_sql(
                "ALTER TABLE devices ADD COLUMN metadata_json JSON NOT NULL DEFAULT '{}'"
            )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
