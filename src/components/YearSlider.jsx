import { useState, useEffect } from "react";

export default function YearSlider({

    year,

    setYear

}){

    const [displayYear, setDisplayYear] = useState(year);

    useEffect(()=>{

        setDisplayYear(year);

    },[year]);

    function handleChange(e){

        setDisplayYear(Number(e.target.value));

    }

    function handleRelease(){

        setYear(displayYear);

    }

    return(

        <div className="yearSlider">

            <div className="yearTitle">

                Selected Year

            </div>

            <div className="yearValue">

                {displayYear}

            </div>

            <input

                type="range"

                min="1980"

                max="2025"

                value={displayYear}

                onChange={handleChange}

                onMouseUp={handleRelease}
                onTouchEnd={handleRelease}

            />

            <div className="yearLabels">

                <span>1980</span>

                <span>2025</span>

            </div>

        </div>

    );

}