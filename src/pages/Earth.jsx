import {

    getClimate,

    average,

    total

} from "../api/climate";


import { useRef, useState, useEffect } from "react";
import { getAIReport } from "../api/ai";
import EarthViewer from "../cesium/Viewer";
import SearchBar from "../components/SearchBar";
import AnalysisPanel from "../components/AnalysisPanel";
import YearSlider from "../components/YearSlider";
import ModeSelector from "../components/ModeSelector";

import { getWeather } from "../api/weather";
import { getBoundary } from "../api/boundary";

export default function Earth() {

    const viewerRef = useRef(null);

    const [analysis, setAnalysis] = useState(null);

    const [year, setYear] = useState(2025);

    const [mode, setMode] = useState("live");

    const [selectedPlace, setSelectedPlace] = useState(null);

    async function handleSearch(place) {

        setSelectedPlace(place);

        if (!viewerRef.current) return;

        viewerRef.current.flyTo(

            Number(place.lat),

            Number(place.lon)

        );

        try {

            if (mode === "live") {

                const weather = await getWeather(

                    place.lat,

                    place.lon

                );

                setAnalysis({

                    mode: "live",

                    name: place.display_name,

                    lat: Number(place.lat),

                    lon: Number(place.lon),

                    temperature: weather.current.temperature_2m,

                    humidity: weather.current.relative_humidity_2m,

                    wind: weather.current.wind_speed_10m,

                    year: year,

                    summary:
                        "Current live weather conditions loaded successfully."

                });

            }

            else if(mode==="climate"){

    const climate = await getClimate(

        place.lat,

        place.lon,

        year

    );

    setAnalysis({

        mode:"climate",

        name:place.display_name,

        lat:Number(place.lat),

        lon:Number(place.lon),

        temperature:

            average(

                climate.daily.temperature_2m_mean

            ),

        humidity:"Coming Soon",

        wind:

            average(

                climate.daily.wind_speed_10m_max

            ),

        rain:

            total(

                climate.daily.precipitation_sum

            ),

        year,

        summary:

            `Climate statistics for ${year}.`

    });

}

            else {

    const prompt = `
You are an environmental scientist.

Location: ${place.display_name}

Latitude: ${place.lat}

Longitude: ${place.lon}

Year: ${year}

Write a professional environmental report.

Include:

Overall Earth Health

Climate risks

Possible future impacts

Recommendations

Maximum 150 words.
`;

    const report = await getAIReport(prompt);

    setAnalysis({

        mode:"ai",

        name:place.display_name,

        lat:Number(place.lat),

        lon:Number(place.lon),

        temperature:"AI",

        humidity:"AI",

        wind:"AI",

        rain:"AI",

        year,

        summary:report

    });

}

        }

        catch (err) {

            console.error(err);

        }

        try {

            const geojson = await getBoundary(

                place.osm_id,

                place.osm_type

            );

            if (

                geojson &&

                viewerRef.current.showBoundary

            ) {

                await viewerRef.current.showBoundary(

                    geojson

                );

            }

        }

        catch (err) {

            console.log("Boundary could not be loaded.");

        }

    }

    useEffect(() => {

        if (!selectedPlace) return;

        handleSearch(selectedPlace);

    }, [mode, year]);

    return (

        <div className="earthPage">

            <SearchBar

                onSearch={handleSearch}

            />

            <ModeSelector

                mode={mode}

                setMode={setMode}

            />

            <EarthViewer

                ref={viewerRef}

            />

            <YearSlider

                year={year}

                setYear={setYear}

            />

            <AnalysisPanel

                data={analysis}

            />

        </div>

    );

}