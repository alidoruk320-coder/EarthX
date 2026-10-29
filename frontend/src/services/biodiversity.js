const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export async function getBiodiversityContext(lat, lon, radiusKm = 50) {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    radius_km: String(radiusKm),
  });
  const response = await fetch(`${API_BASE}/biodiversity?${params}`);
  if (!response.ok) {
    throw new Error(`Biodiversity context request failed (${response.status}).`);
  }
  return response.json();
}
