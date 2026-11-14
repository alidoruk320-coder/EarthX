const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export async function analyzeSwotLake(lat, lon, startYear, endYear) {
  const response = await fetch(`${API_BASE}/analyze-swot-lake`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lat: Number(lat),
      lon: Number(lon),
      start_year: startYear,
      end_year: endYear,
    }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || `SWOT API error (${response.status})`);
  }
  return response.json();
}
