import math
from numbers import Real

from fastapi.responses import JSONResponse


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, Real) and not isinstance(value, bool):
        return value if math.isfinite(value) else None
    return value


class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(json_safe(content))
