from sqlalchemy import inspect, text

from app.database import Base, engine, init_database


def test_init_database_migrates_existing_devices_table_idempotently():
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE devices (
                id INTEGER NOT NULL PRIMARY KEY,
                plot_id INTEGER NOT NULL,
                device_code VARCHAR(100) NOT NULL,
                name VARCHAR(100) NOT NULL,
                device_type VARCHAR(50) NOT NULL,
                communication_type VARCHAR(30) NOT NULL,
                is_online BOOLEAN NOT NULL,
                last_seen_at DATETIME,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.execute(
            text(
                """
                INSERT INTO devices (
                    id, plot_id, device_code, name, device_type,
                    communication_type, is_online, created_at
                ) VALUES (
                    1, 1, 'legacy-pump', '旧水泵', 'pump',
                    'http', 0, '2026-07-22 00:00:00'
                )
                """
            )
        )

    init_database()
    init_database()

    with engine.connect() as connection:
        columns = [
            column["name"] for column in inspect(connection).get_columns("devices")
        ]
        row = connection.execute(
            text(
                "SELECT actuator_state, state_updated_at "
                "FROM devices WHERE device_code = 'legacy-pump'"
            )
        ).one()

    assert columns.count("actuator_state") == 1
    assert columns.count("state_updated_at") == 1
    assert row.actuator_state == "unknown"
    assert row.state_updated_at is None
