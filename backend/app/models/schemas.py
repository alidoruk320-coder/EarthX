from pydantic import BaseModel, Field


class PointAnalysisRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    variable: str = Field(min_length=1)
    start_year: int = Field(default=2002, ge=1970, le=2100)
    end_year: int = Field(default=2025, ge=1970, le=2100)


class SeriesAnalysisRequest(BaseModel):
    variable: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    start_year: int = Field(ge=1970, le=2100)
    end_year: int = Field(ge=1970, le=2100)
    series: list[dict]


class RegionAnalysisRequest(BaseModel):
    geometry: dict
    variable: str = Field(min_length=1)
    start_year: int = Field(ge=1970, le=2100)
    end_year: int = Field(ge=1970, le=2100)


class CascadeRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    variable_a: str = Field(min_length=1)
    variable_b: str = Field(min_length=1)
    start_year: int = Field(default=2002, ge=1970, le=2100)
    end_year: int = Field(default=2025, ge=1970, le=2100)
    max_lag_years: int = Field(default=6, ge=0, le=20)
