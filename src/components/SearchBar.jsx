import { useEffect, useState } from "react";

import { searchPlace } from "../api/geocoder";

export default function SearchBar({ onSearch }) {

    const [text, setText] = useState("");

    const [results, setResults] = useState([]);

    const [loading, setLoading] = useState(false);

    useEffect(() => {

        if (text.trim().length < 2) {

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

    function selectPlace(place) {

        setText(place.display_name);

        setResults([]);

        onSearch(place);

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

                    placeholder="Search country or city..."

                    value={text}

                    onChange={(e) => setText(e.target.value)}

                    onKeyDown={handleEnter}

                />

                <button

                    onClick={() => {

                        if (results.length > 0) {

                            selectPlace(results[0]);

                        }

                    }}

                >

                    Search

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

                    Searching...

                </div>

            }

        </div>

    );

}