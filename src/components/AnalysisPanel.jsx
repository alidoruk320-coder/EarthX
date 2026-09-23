// src/components/AnalysisPanel.jsx
import React from "react";

export default function AnalysisPanel({ data }) {
  if (!data) {
    return (
      <div className="analysisPanel">
        <h2>🌍 Earth Scanner Ready</h2>
        <p>Select a location on the 3D globe or search a region, then click <strong>SCAN EARTH</strong> to run the Significance Engine.</p>
      </div>
    );
  }

  const { name, variable, stats, summary, contrast } = data;

  return (
    <div className="analysisPanel" style={{ width: '380px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <h2 style={{ margin: 0, fontSize: '18px', color: '#eef5f7' }}>{name}</h2>
        <span style={{ fontSize: '11px', background: '#17374a', padding: '3px 8px', border: '1px solid #4b6571', borderRadius: '4px' }}>
          {variable || "Ecosystem"}
        </span>
      </div>

      <div style={{ fontSize: '12px', color: '#a8c0ca', marginBottom: '14px' }}>
        Period: <strong>2002 – 2026</strong> | NASA Earth Observations
      </div>

      {stats && (
        <div style={{ marginBottom: '14px' }}>
          <div className="analysisGrid">
            <div className="infoCard">
              <span>Trend Direction</span>
              <strong style={{ color: stats.slope >= 0 ? '#75b77a' : '#e06c75' }}>
                {stats.trend}
              </strong>
            </div>
            <div className="infoCard">
              <span>Sen's Slope (Magnitude)</span>
              <strong>{stats.slope} /yr</strong>
            </div>
          </div>

          <div className="analysisGrid" style={{ marginTop: '8px' }}>
            <div className="infoCard">
              <span>Mann-Kendall Z</span>
              <strong>{stats.zScore}</strong>
            </div>
            <div className="infoCard">
              <span>p-value</span>
              <strong>{stats.pValue}</strong>
            </div>
          </div>

          <div style={{ 
            marginTop: '10px', 
            padding: '10px', 
            textAlign: 'center',
            borderRadius: '4px',
            fontWeight: '700',
            fontSize: '13px',
            background: stats.significant ? 'rgba(117, 183, 122, 0.2)' : 'rgba(224, 108, 117, 0.2)',
            border: `1px solid ${stats.significant ? '#75b77a' : '#e06c75'}`,
            color: stats.significant ? '#a3d9a5' : '#f0939b'
          }}>
            {stats.significant ? "✓ STATISTICALLY SIGNIFICANT" : "✗ NOT STATISTICALLY SIGNIFICANT"}
          </div>
        </div>
      )}

      {contrast && (
        <div className="aiCard" style={{ borderColor: '#61afef', background: 'rgba(97, 175, 239, 0.1)' }}>
          <h3 style={{ color: '#61afef' }}>⚡ Regional Contrast Detected</h3>
          <p style={{ fontSize: '13px' }}>{contrast}</p>
        </div>
      )}

      <div className="aiCard">
        <h3>🤖 AI Investigator Report</h3>
        <p style={{ fontSize: '13px', lineHeight: '1.5' }}>{summary}</p>
        <div style={{ marginTop: '8px', fontSize: '10px', color: '#7f98a3', fontStyle: 'italic' }}>
          *Note: Correlation does not establish causation. Model-based inference.
        </div>
      </div>
    </div>
  );
}