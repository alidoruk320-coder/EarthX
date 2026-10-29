const BASE = "https://archive-api.open-meteo.com/v1/archive";

export async function getClimate(lat, lon, year) {

    const start = `${year}-01-01`;
    const end = `${year}-12-31`;

    const url =
`${BASE}?latitude=${lat}&longitude=${lon}&start_date=${start}&end_date=${end}&daily=temperature_2m_mean,precipitation_sum,wind_speed_10m_max`;

    const response = await fetch(url);

    if (!response.ok) {

        throw new Error("Climate API Error");

    }

    return await response.json();

}

export function average(values){

    if(!values || values.length===0){

        return "--";

    }

    return (

        values.reduce((a,b)=>a+b,0)

        /

        values.length

    ).toFixed(1);

}

export function total(values){

    if(!values || values.length===0){

        return "--";

    }

    return values

    .reduce((a,b)=>a+b,0)

    .toFixed(1);

}