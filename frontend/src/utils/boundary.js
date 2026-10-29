export async function getBoundary(place) {

    if (!place.osm_id || !place.osm_type) {

        return null;

    }

    let type = "";

    switch (place.osm_type) {

        case "relation":
        case "R":

            type = "relation";
            break;

        case "way":
        case "W":

            type = "way";
            break;

        default:

            return null;

    }

    const query = `
[out:json];
${type}(${place.osm_id});
out geom;
`;

    const response = await fetch(

        "https://overpass-api.de/api/interpreter",

        {

            method: "POST",

            body: query

        }

    );

    if (!response.ok) {

        throw new Error("Boundary API Error");

    }

    const data = await response.json();

    if (!data.elements || data.elements.length === 0) {

        return null;

    }

    const element = data.elements[0];

    if (!element.geometry) {

        return null;

    }

    return element.geometry.map(point => [

        point.lon,

        point.lat

    ]);

}