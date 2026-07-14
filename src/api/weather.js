const BASE = "https://api.open-meteo.com/v1/forecast";

export async function getWeather(lat, lon) {

    const url =
`${BASE}?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m`;

    const response = await fetch(url);

    if (!response.ok) {

        throw new Error("Weather API Error");

    }

    return await response.json();

}