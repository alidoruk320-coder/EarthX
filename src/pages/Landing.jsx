// src/pages/Landing.jsx
function Landing({ onEnter }) {
  const assetBase = import.meta.env.BASE_URL;

  return (
    <div className="landing">
      <div className="stars"></div>

      <div className="topLogo">
        <img src={`${assetBase}images/logo.png`} alt="Logo" />
        <span>NexusEarth 3D</span>
      </div>

      <div className="powered">
        NASA Space Apps Challenge 2026
      </div>

      <div className="landingContent">
        <div className="badge">
          WHAT CHANGED? WHERE? HOW MUCH? IS IT SIGNIFICANT?
        </div>

        <h1>NEXUSEARTH 3D</h1>
        <p className="subtitle" style={{ fontWeight: 600, color: '#8fc8da', marginBottom: '12px' }}>
          AI-Assisted Earth System Trend Detective
        </p>

        <p className="subtitle">
          An interactive 3D Earth system powered by NASA observations. 
          We don't just show change — we quantify, compare, and investigate 
          statistically significant environmental trends across space and time.
        </p>

        <button onClick={onEnter}>
          SCAN EARTH & DETECT TRENDS ➔
        </button>

        <div className="features">
          <div className="featureCard">
            <div className="icon">01 / DETECT</div>
            <h3>Significance Engine</h3>
            <p>Sen's Slope & Mann-Kendall rigorous statistical testing.</p>
          </div>

          <div className="featureCard">
            <div className="icon">02 / COMPARE</div>
            <h3>Contrast Detector</h3>
            <p>Discover regional opposites and concurrent shifts automatically.</p>
          </div>

          <div className="featureCard">
            <div className="icon">03 / INVESTIGATE</div>
            <h3>AI Investigator</h3>
            <p>Contextual AI reports respecting scientific boundaries.</p>
          </div>
        </div>
      </div>

      <div className="earthHero">
        <img src={`${assetBase}images/earth.png`} alt="Earth" />
      </div>
    </div>
  );
}

export default Landing;