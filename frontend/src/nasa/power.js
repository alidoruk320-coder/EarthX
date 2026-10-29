export async function getPowerData(lat, lon) {

    const url =
        `https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=T2M,PRECTOTCORR,ALLSKY_SFC_SW_DWN&community=RE&longitude=${lon}&latitude=${lat}&format=JSON`;

    try {

        const response = await fetch(url);

        const json = await response.json();

        const data = json.properties.parameter;

        return {

            temperature:
                data.T2M.ANN,

            rainfall:
                data.PRECTOTCORR.ANN,

            solar:
                data.ALLSKY_SFC_SW_DWN.ANN

        };

    }

    catch (e) {

        console.error(e);

        return null;

    }

}

export const NASA_POWER_SERIES = {
    "Temperature": { parameter: "T2M", unit: "°C (annual mean of daily values)" },
    "Precipitation": { parameter: "PRECTOTCORR", unit: "mm/day (annual mean)" },
};

export async function getNasaPowerSeries(lat, lon, variable, startYear, endYear) {
    const source = NASA_POWER_SERIES[variable];
    if (!source) return null;
    const parameter = source.parameter;

    const url = `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=${parameter}&community=RE&longitude=${lon}&latitude=${lat}&start=${startYear}0101&end=${endYear}1231&format=JSON&header=true&time-standard=UTC`;
    const response = await fetch(url);
    if (!response.ok) throw new Error("NASA POWER series request failed");

    const json = await response.json();
    const values = json?.properties?.parameter?.[parameter] || {};
    const byYear = new Map();

    Object.entries(values).forEach(([date, value]) => {
        const numericValue = Number(value);
        if (!Number.isFinite(numericValue) || numericValue <= -999) return;
        const year = Number(date.slice(0, 4));
        if (!byYear.has(year)) byYear.set(year, []);
        byYear.get(year).push(numericValue);
    });

    return Array.from(byYear.entries()).filter(([year, yearValues]) => {
        const daysInYear = new Date(Date.UTC(year + 1, 0, 1) - Date.UTC(year, 0, 1)).getTime() / 86400000;
        return yearValues.length >= Math.ceil(daysInYear * 0.9);
    }).map(([year, yearValues]) => ({
        year,
        value: Number((yearValues.reduce((sum, value) => sum + value, 0) / yearValues.length).toFixed(3)),
    })).sort((first, second) => first.year - second.year);
}
