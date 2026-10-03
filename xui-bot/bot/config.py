import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: Path) -> None:
    """Minimal KEY=VALUE loader. No interpolation, so URL-encoded values stay intact."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset
    panel_url: str
    panel_token: str
    panel_verify_ssl: bool
    inbound_remark: str
    inbound_id: int | None
    traffic_gb: int
    low_traffic_gb: float
    extra_traffic_gb: int
    traffic_check_minutes: int
    cdn_domain: str
    vless_template: str
    sub_url: str
    db_path: Path

    @classmethod
    def load(cls) -> "Config":
        load_env_file(Path(os.environ.get("ENV_FILE", ".env")))
        missing = [k for k in ("BOT_TOKEN", "PANEL_URL", "PANEL_TOKEN", "ADMIN_IDS") if not os.environ.get(k)]
        if missing:
            raise SystemExit(f"Missing required settings in .env: {', '.join(missing)}")
        inbound_id = os.environ.get("INBOUND_ID", "").strip()
        return cls(
            bot_token=os.environ["BOT_TOKEN"].strip(),
            admin_ids=frozenset(int(x) for x in os.environ["ADMIN_IDS"].split(",") if x.strip()),
            panel_url=os.environ["PANEL_URL"].strip().rstrip("/"),
            panel_token=os.environ["PANEL_TOKEN"].strip(),
            panel_verify_ssl=_bool(os.environ.get("PANEL_VERIFY_SSL", "true")),
            inbound_remark=os.environ.get("INBOUND_REMARK", "AltynCDN").strip(),
            inbound_id=int(inbound_id) if inbound_id else None,
            traffic_gb=int(os.environ.get("TRAFFIC_GB", "15")),
            low_traffic_gb=float(os.environ.get("LOW_TRAFFIC_GB", "2")),
            extra_traffic_gb=int(os.environ.get("EXTRA_TRAFFIC_GB", "5")),
            traffic_check_minutes=max(1, int(os.environ.get("TRAFFIC_CHECK_MINUTES", "30"))),
            cdn_domain=os.environ.get("CDN_DOMAIN", "").strip(),
            vless_template=os.environ.get("VLESS_TEMPLATE", "").strip(),
            sub_url=os.environ.get("SUB_URL", "").strip(),
            db_path=Path(os.environ.get("DB_PATH", "data/bot.db")),
        )
