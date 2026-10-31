import { useEffect, useRef, useState } from "react";

import { resolvePlaceBoundary, searchPlace } from "../api/geocoder";

export default function SearchBar({ onSearch, language = "en" }) {
    const isTurkish = language === "tr";

    const [text, setText] = useState("");

    const [results, setResults] = useState([]);

    const [loading, setLoading] = useState(false);
    const selectedTextRef = useRef("");

    useEffect(() => {

        if (text.trim().length < 2 || text === selectedTextRef.current) {

            setResults([]);
            return;

        }

        const timeout = setTimeout(async () => {

            try {

                setLoading(true);

                const places = await searchPlace(text);

                setResults(places);

            } catch (err) {

                console.error(err);

            } finally {

                setLoading(false);

            }

        }, 300);

        return () => clearTimeout(timeout);

    }, [text]);

    async function selectPlace(place) {
        setLoading(true);
        setText(place.display_name);
        setResults([]);
        selectedTextRef.current = place.display_name;
        try {
            const resolvedPlace = await resolvePlaceBoundary(place, text);
            onSearch(resolvedPlace);
        } catch (error) {
            console.warn("Boundary resolution did not complete; using the original place result:", error);
            onSearch({ ...place, boundary_warning: "boundary_unavailable_bbox_fallback" });
        } finally {
            setLoading(false);
        }

    }

    function handleEnter(e) {

        if (e.key === "Enter" && results.length > 0) {

            selectPlace(results[0]);

        }

    }

    return (

        <div className="searchWrapper">

            <div className="searchBar">

                <input

                    type="text"

                    placeholder={isTurkish ? "Ülke, şehir veya bölge ara..." : "Search country or city..."}

                    value={text}

                    onChange={(e) => {
                        selectedTextRef.current = "";
                        setText(e.target.value);
                    }}

                    onKeyDown={handleEnter}

                />

                <button

                    onClick={() => {

                        if (results.length > 0) {

                            selectPlace(results[0]);

                        }

                    }}

                >

                    {isTurkish ? "Ara" : "Search"}

                </button>

            </div>

            {

                results.length > 0 &&

                <div className="suggestions">

                    {

                        results.map((place) => (

                            <div

                                key={place.place_id}

                                className="suggestion"

                                onClick={() => selectPlace(place)}

                            >

                                <strong>

                                    {place.display_name.split(",")[0]}

                                </strong>

                                <br />

                                <small>

                                    {place.display_name}

                                </small>

                            </div>

                        ))

                    }

                </div>

            }

            {

                loading &&

                <div className="loadingSearch">

                    {isTurkish ? "Aranıyor..." : "Searching..."}

                </div>

            }

        </div>

    );

}
