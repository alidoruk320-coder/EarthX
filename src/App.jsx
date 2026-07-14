import { useState } from "react";

import Landing from "./pages/Landing";
import Earth from "./pages/Earth";

function App() {

  const [entered, setEntered] = useState(false);

  return (
    <>
      {entered ? (
        <Earth />
      ) : (
        <Landing onEnter={() => setEntered(true)} />
      )}
    </>
  );

}

export default App;