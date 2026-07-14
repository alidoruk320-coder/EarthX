export default function ModeSelector({

    mode,

    setMode

}){

    return(

        <div className="modeSelector">

            <button

                className={mode==="live"?"active":""}

                onClick={()=>setMode("live")}

            >

                🌦 Live

            </button>

            <button

                className={mode==="climate"?"active":""}

                onClick={()=>setMode("climate")}

            >

                🌍 Climate

            </button>

            <button

                className={mode==="ai"?"active":""}

                onClick={()=>setMode("ai")}

            >

                🤖 AI Report

            </button>

        </div>

    );

}