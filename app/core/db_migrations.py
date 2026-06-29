from sqlalchemy import inspect, text

from app.core.database import engine


VIDEO_TASK_COLUMNS: dict[str, str] = {
    "source": "VARCHAR(32)",
    "external_record_id": "VARCHAR(128)",
    "feishu_app_token": "VARCHAR(128)",
    "feishu_table_id": "VARCHAR(128)",
    "feishu_record_id": "VARCHAR(128)",
    "video_url": "VARCHAR(1024)",
    "cover_path": "VARCHAR(512)",
    "cover_url": "VARCHAR(1024)",
    "storage_provider": "VARCHAR(32)",
    "storage_bucket": "VARCHAR(128)",
    "video_object_name": "VARCHAR(512)",
    "cover_object_name": "VARCHAR(512)",
    "callback_status": "VARCHAR(32)",
    "callback_error": "TEXT",
    "provider": "VARCHAR(32)",
    "remote_task_id": "VARCHAR(128)",
    "provider_response": "JSON",
    "download_url": "VARCHAR(1024)",
    "provider_cost": "FLOAT",
    "provider_status": "VARCHAR(32)",
}


def run_db_migrations() -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "video_tasks" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("video_tasks")}
    missing_columns = [
        (name, column_type)
        for name, column_type in VIDEO_TASK_COLUMNS.items()
        if name not in existing_columns
    ]
    if not missing_columns:
        return

    with engine.begin() as connection:
        for name, column_type in missing_columns:
            connection.execute(text(f"ALTER TABLE video_tasks ADD COLUMN {name} {column_type}"))
