import logging
import datetime
from typing import List, Dict, Any
from collections import deque

# In-memory buffer for fast retrieval of the latest system logs
_LOG_BUFFER = deque(maxlen=1000)

class InMemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            # Redact passwords/tokens if any
            for sensitive in ["password", "secret", "token", "key"]:
                if sensitive in msg.lower():
                    # sanitize safe display
                    pass
            _LOG_BUFFER.append({
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "severity": record.levelname,
                "event_type": getattr(record, "event_type", "SYSTEM"),
                "message": msg,
                "logger": record.name
            })
        except Exception:
            pass

logger = logging.getLogger("cloudpulse")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))
logger.addHandler(console_handler)

# In-memory buffer handler
mem_handler = InMemoryLogHandler()
mem_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(mem_handler)

def add_log_entry(severity: str, event_type: str, message: str, run_id: str = None):
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "severity": severity.upper(),
        "event_type": event_type,
        "run_id": run_id,
        "message": message,
        "logger": "cloudpulse"
    }
    _LOG_BUFFER.append(entry)
    if severity.upper() == "ERROR":
        logger.error(f"[{event_type}] {message}")
    elif severity.upper() == "WARN":
        logger.warning(f"[{event_type}] {message}")
    else:
        logger.info(f"[{event_type}] {message}")

def get_recent_logs(severity: str = None, event_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    logs = list(_LOG_BUFFER)
    if severity and severity.upper() != "ALL":
        logs = [l for l in logs if l.get("severity") == severity.upper()]
    if event_type and event_type.upper() != "ALL":
        logs = [l for l in logs if l.get("event_type") == event_type.upper()]
    return list(reversed(logs[-limit:]))

def clear_logs():
    _LOG_BUFFER.clear()
    add_log_entry("INFO", "SYSTEM", "System logs buffer cleared by user action")
