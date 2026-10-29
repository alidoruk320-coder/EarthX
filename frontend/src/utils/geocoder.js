export async function searchLocation(query) {

    if (!query) return [];

    const url =
        `https://nominatim.openstreetmap.org/search?format=jsonv2&q=${encodeURIComponent(query)}&limit=8`;

    const response = await fetch(url, {
        headers: {
            "Accept": "application/json"
        }
    });

    const data = await response.json();

    return data;
}