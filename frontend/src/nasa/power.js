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
    "MERRA-2 Air Temperature": {
        parameter: "T2M",
        unit: "°C (annual mean)",
        temporal: "monthly",
        datasetId: "NASA POWER Monthly MERRA-2 · T2M",
    },
    "MERRA-2 Evapotranspiration Energy Flux": {
        parameter: "EVPTRNS",
        unit: "MJ/m²/day (annual mean)",
        scaleFactor: 3.6,
        temporal: "monthly",
        datasetId: "NASA POWER Monthly MERRA-2 · EVPTRNS",
    },
};

const MONTHLY_REQUEST_TIMEOUT_MS = 45_000;

function validPowerValue(value) {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) && numericValue > -999;
}

function annualizeMonthlyValues(values, startYear, endYear, source) {
    const series = [];
    for (let year = startYear; year <= endYear; year += 1) {
        const annualValue = values[`${year}13`];
        if (validPowerValue(annualValue)) {
            series.push({ year, value: Number((Number(annualValue) * (source.scaleFactor || 1)).toFixed(3)) });
            continue;
        }

        const monthlyValues = Array.from({ length: 12 }, (_, index) => values[`${year}${String(index + 1).padStart(2, "0")}`]);
        if (!monthlyValues.every(validPowerValue)) continue;
        const daysInYear = new Date(Date.UTC(year + 1, 0, 1) - Date.UTC(year, 0, 1)).getTime() / 86400000;
        const weightedMean = monthlyValues.reduce((sum, value, index) => {
            const monthDays = new Date(Date.UTC(year, index + 1, 0)).getUTCDate();
            return sum + Number(value) * monthDays;
        }, 0) / daysInYear;
        series.push({
            year,
            value: Number((weightedMean * (source.scaleFactor || 1)).toFixed(3)),
        });
    }
    return series;
}

async function getNasaPowerMonthlySeries(lat, lon, variable, startYear, endYear, source) {
    const params = new URLSearchParams({
        parameters: source.parameter,
        community: "RE",
        longitude: String(lon),
        latitude: String(lat),
        start: String(startYear),
        end: String(endYear),
        format: "JSON",
    });
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), MONTHLY_REQUEST_TIMEOUT_MS);
    let json;
    try {
        const response = await fetch(
            `https://power.larc.nasa.gov/api/temporal/monthly/point?${params}`,
            { signal: controller.signal },
        );
        if (!response.ok) throw new Error(`NASA POWER monthly request failed (${response.status})`);
        json = await response.json();
    } catch (error) {
        if (controller.signal.aborted) {
            const timeoutError = new Error("NASA POWER monthly request exceeded 45 seconds");
            timeoutError.code = "NASA_POWER_TIMEOUT";
            throw timeoutError;
        }
        throw error;
    } finally {
        clearTimeout(timeoutId);
    }

    const values = json?.properties?.parameter?.[source.parameter];
    if (!values || typeof values !== "object") {
        throw new Error(`NASA POWER response is missing ${source.parameter} data for ${variable}`);
    }
    return annualizeMonthlyValues(values, startYear, endYear, source);
}

export async function getNasaPowerSeries(lat, lon, variable, startYear, endYear) {
    const source = NASA_POWER_SERIES[variable];
    if (!source) return null;
    if (source.temporal === "monthly") {
        return getNasaPowerMonthlySeries(lat, lon, variable, startYear, endYear, source);
    }
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
