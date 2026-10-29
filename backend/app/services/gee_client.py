import ee
from pathlib import Path
from app.config import GEE_SERVICE_ACCOUNT_EMAIL, GEE_PRIVATE_KEY, GEE_PRIVATE_KEY_PATH, GEE_PROJECT_ID

_initialized = False


def init_gee():
    """Uygulama başlarken bir kez çağrılır (main.py -> startup event)."""
    global _initialized
    if _initialized:
        return True

    if not GEE_SERVICE_ACCOUNT_EMAIL or not GEE_PROJECT_ID:
        return False

    if GEE_PRIVATE_KEY:
        credentials = ee.ServiceAccountCredentials(
            email=GEE_SERVICE_ACCOUNT_EMAIL,
            key_data=GEE_PRIVATE_KEY.replace("\\n", "\n"),
        )
    elif GEE_PRIVATE_KEY_PATH:
        key_path = Path(GEE_PRIVATE_KEY_PATH)
        if not key_path.is_absolute():
            key_path = (Path(__file__).resolve().parents[2] / key_path).resolve()
        if not key_path.is_file():
            return False
        credentials = ee.ServiceAccountCredentials(
            email=GEE_SERVICE_ACCOUNT_EMAIL,
            key_file=str(key_path),
        )
    else:
        return False
    ee.Initialize(credentials, project=GEE_PROJECT_ID)
    _initialized = True
    return True


def is_gee_initialized():
    return _initialized
