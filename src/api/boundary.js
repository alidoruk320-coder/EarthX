const OVERPASS = "https://overpass-api.de/api/interpreter";

export async function getBoundary(osm_id, osm_type) {

    let type = "";

    if (osm_type === "relation" || osm_type === "R") {

        type = "relation";

    } else if (osm_type === "way" || osm_type === "W") {

        type = "way";

    } else {

        return null;

    }

    const query = `
[out:json];
${type}(${osm_id});
out geom;
`;

    const response = await fetch(OVERPASS, {
        method: "POST",
        body: query
    });

    if (!response.ok) {

        throw new Error("Boundary API Error");

    }

    const data = await response.json();
    console.log(data);

    if (!data.elements || data.elements.length === 0) {

        return null;

    }

    const element = data.elements[0];

    if (!element.geometry) {

        return null;

    }

    const coordinates = element.geometry.map(point => [

        point.lon,

        point.lat

    ]);

    return {

        type: "FeatureCollection",

        features: [

            {

                type: "Feature",

                geometry: {

                    type: "Polygon",

                    coordinates: [

                        coordinates

                    ]

                },

                properties: {}

            }

        ]

    };

}