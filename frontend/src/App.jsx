import { lazy, Suspense, useState } from "react";

const Landing = lazy(() => import("./pages/Landing"));
const Earth = lazy(() => import("./pages/Earth"));
const GlobalStory = lazy(() => import("./pages/GlobalStory"));

function App() {

  const [entered, setEntered] = useState(false);
  const [showStory, setShowStory] = useState(false);
  const [language, setLanguage] = useState("en");

  return (
    <Suspense fallback={<main className="appLoading" role="status">Loading Earth data…</main>}>
      {entered ? (
        showStory
          ? <GlobalStory language={language} onBack={() => setShowStory(false)} />
          : <Earth
            language={language}
            setLanguage={setLanguage}
            onOpenStory={() => setShowStory(true)}
          />
      ) : (
        <Landing onEnter={() => setEntered(true)} language={language} setLanguage={setLanguage} />
      )}
    </Suspense>
  );

}

export default App;
