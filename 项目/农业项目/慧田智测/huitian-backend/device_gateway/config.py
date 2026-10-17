from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    mode: str = "http"
    api_base_url: str = "http://172.20.10.5:8000"
    device_code: str = "weather-001"
    interval_seconds: float = 5.0
    mqtt_host: str = "172.20.10.5"
    mqtt_port: int = 1883
    mqtt_topic_prefix: str = "huitian"

    model_config = SettingsConfigDict(env_prefix="GATEWAY_", env_file=".env", extra="ignore")


gateway_settings = GatewaySettings()
