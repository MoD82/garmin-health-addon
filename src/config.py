from pathlib import Path
import json
from pydantic import BaseModel

OPTIONS_PATH = Path("/data/options.json")


class Config(BaseModel):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    email_user: str = ""
    email_password: str = ""
    email_recipient: str = ""
    garmin_user: str = ""
    garmin_password: str = ""
    analysis_time: str = "08:00"
    collection_time: str = "07:30"
    weekly_report_day: str = "monday"
    weekly_report_time: str = "08:00"
    timezone: str = "Europe/Berlin"
    retry_count: int = 3
    retry_interval_minutes: int = 15


def load_config() -> Config:
    if OPTIONS_PATH.exists():
        data = json.loads(OPTIONS_PATH.read_text())
        return Config(**data)
    return Config()
