function Landing({ onEnter }) {
  return (
    <div className="landing">

      <div className="stars"></div>

      <div className="topLogo">
        <img src="/images/logo.png" alt="Logo" />
        <span>EarthVerse AI</span>
      </div>

      <div className="powered">
        Powered by NASA Open Data
      </div>

      <div className="landingContent">

        <img
          src="/images/logo.png"
          className="logo"
          alt="EarthVerse AI"
        />

        <div className="badge">
          NASA • Cesium • Artificial Intelligence
        </div>

        <h1>EARTHVERSE AI</h1>

        <p className="subtitle">
          Explore Earth with real satellite imagery,
          historical climate data,
          AI-powered explanations
          and interactive 3D visualization.
        </p>

        <button onClick={onEnter}>
          ENTER EXPERIENCE
        </button>

        <div className="features">

          <div className="featureCard">
            <div className="icon">🌍</div>
            <h3>3D Earth</h3>
            <p>Interactive globe powered by Cesium.</p>
          </div>

          <div className="featureCard">
            <div className="icon">🛰️</div>
            <h3>NASA Data</h3>
            <p>Historical satellite imagery and climate layers.</p>
          </div>

          <div className="featureCard">
            <div className="icon">🤖</div>
            <h3>AI Analysis</h3>
            <p>Automatic explanations of environmental changes.</p>
          </div>

        </div>

      </div>

      <div className="earthHero">
        <img src="/images/earth.png" alt="Earth" />
      </div>

    </div>
  );
}

export default Landing;