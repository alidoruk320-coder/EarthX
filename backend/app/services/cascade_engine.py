import math
from typing import Dict, List, Optional

from scipy.stats import pearsonr

INSUFFICIENT_DATA_MESSAGE = (
    "Seçilen bölge/tarih aralığında bir veya iki değişken için yeterli veri bulunamadı, "
    "korelasyon hesaplanamadı."
)


def insufficient_data_result() -> dict:
    return {
        "significant": False,
        "message": INSUFFICIENT_DATA_MESSAGE,
    }


def _numeric_year_series(series: Optional[List[Dict]]) -> Dict[int, float]:
    values_by_year = {}
    if not isinstance(series, list):
        return values_by_year

    for point in series:
        if not isinstance(point, dict):
            continue

        year = point.get("year")
        if year is None and isinstance(point.get("date"), str):
            year = point["date"][:4]

        try:
            year = int(year)
            value = float(point["value"])
        except (KeyError, TypeError, ValueError):
            continue

        if math.isfinite(value):
            values_by_year[year] = value

    return values_by_year


def lagged_cross_correlation(series_a: list[dict], series_b: list[dict],
                              max_lag_years: int = 6) -> dict:
    """
    Yıllık gözlemleri yıl anahtarına göre hizalar. İlişki, tek başına
    nedensellik kanıtı değildir.
    """
    values_a = _numeric_year_series(series_a)
    values_b = _numeric_year_series(series_b)
    common_years = sorted(set(values_a) & set(values_b))
    if len(common_years) < 10:
        return insufficient_data_result()

    best = None
    tested_lags = 0
    max_lag_years = max(0, int(max_lag_years))

    for lag in range(0, max_lag_years + 1):
        paired_years = [year for year in common_years if year + lag in values_b]
        if len(paired_years) < 10:
            continue

        a = [values_a[year] for year in paired_years]
        b = [values_b[year + lag] for year in paired_years]
        if len(set(a)) < 2 or len(set(b)) < 2:
            continue

        try:
            r, p = pearsonr(a, b)
        except (ValueError, FloatingPointError):
            continue

        if not math.isfinite(r) or not math.isfinite(p):
            continue

        tested_lags += 1
        if best is None or abs(r) > abs(best["r"]):
            best = {"lag": lag, "r": float(r), "p": float(p)}

    if best is None:
        return insufficient_data_result()

    adjusted_p = min(1.0, best["p"] * tested_lags)
    significant = adjusted_p < 0.05
    correlation = round(best["r"], 3)

    return {
        "lag_steps": best["lag"],
        "lag_years": best["lag"],
        "correlation": correlation,
        "p_value": round(best["p"], 5),
        "adjusted_p_value": round(adjusted_p, 5),
        "significant": significant,
        "common_observation_count": len(common_years),
        "tested_lag_count": tested_lags,
        "method_note": "Pearson p-values are Bonferroni-adjusted across tested lags; serial autocorrelation in annual environmental series is not modeled and can inflate significance.",
        "message": (
            f"{best['lag']} yıl gecikmeyle anlamlı ilişki tespit edildi (r={correlation}); gecikmeler için Bonferroni düzeltmesi uygulanmıştır, ancak yıllık serilerde otokorelasyon modellenmediğinden p-değeri iyimser olabilir. Bu sonuç nedensellik kanıtı değildir."
            if significant else
            "No statistically significant connection detected after lag adjustment. Annual-series autocorrelation is not modeled, and correlation does not establish causation."
        ),
    }
