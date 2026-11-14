import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.swot_lakes import (  # noqa: E402
    CACHE_PATH,
    EARLIEST_DATA_YEAR,
    HYDROCRON_COLLECTION,
    HYDROCRON_ENDPOINT,
    HYDROCRON_FIELDS,
    SWOT_LAKES,
    parse_hydrocron_csv,
)


def fetch_lake_observations(lake_id: str, end_time: str) -> list[dict]:
    parameters = {
        "feature": "PriorLake",
        "feature_id": lake_id,
        "collection_name": HYDROCRON_COLLECTION,
        "start_time": f"{EARLIEST_DATA_YEAR}-01-01T00:00:00Z",
        "end_time": end_time,
        "output": "csv",
        "fields": HYDROCRON_FIELDS,
    }
    request = Request(
        f"{HYDROCRON_ENDPOINT}?{urlencode(parameters)}",
        headers={"Accept": "application/json", "User-Agent": "EarthVerse/1.0"},
    )
    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not str(payload.get("status", "")).startswith("200"):
        raise RuntimeError(f"Hydrocron returned an unsuccessful status for lake {lake_id}: {payload.get('status')}")
    csv_content = payload.get("results", {}).get("csv")
    if not isinstance(csv_content, str):
        raise RuntimeError(f"Hydrocron response for lake {lake_id} did not include CSV observations")
    observations = parse_hydrocron_csv(csv_content, lake_id)
    if not observations:
        raise RuntimeError(f"Hydrocron returned no valid SWOT observations for lake {lake_id}")
    return observations


def main() -> None:
    end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")
    lakes = {}
    for key, definition in SWOT_LAKES.items():
        observations = fetch_lake_observations(definition["lake_id"], end_time)
        lakes[key] = {
            **definition,
            "observations": observations,
        }
        print(f"{definition['lake_name']}: {len(observations)} valid observations")

    cache = {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_endpoint": HYDROCRON_ENDPOINT,
        "collection": HYDROCRON_COLLECTION,
        "lakes": lakes,
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = CACHE_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(cache, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(CACHE_PATH)
    print(f"Updated cache: {CACHE_PATH}")


if __name__ == "__main__":
    main()
