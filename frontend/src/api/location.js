export async function getLocationInfo(lat, lon) {

    const url =
`https://api.open-meteo.com/v1/elevation?latitude=${lat}&longitude=${lon}`;

    const res = await fetch(url);

    if (!res.ok) {

        throw new Error("Location API Error");

    }

    return await res.json();

}