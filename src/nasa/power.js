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