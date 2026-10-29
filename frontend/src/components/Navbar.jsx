// src/components/Navbar.jsx
import React from "react";

export default function Navbar({ currentMode, setMode }) {
  const modes = [
    { id: "explore", label: "🌍 EXPLORE" },
    { id: "compare", label: "⚖️ COMPARE (Twin View)" },
    { id: "story", label: "📖 STORY MODE" },
    { id: "scan", label: "🔍 SCAN EARTH" }
  ];

  return (
    <div style={{
      position: 'absolute',
      top: '16px',
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 100000,
      display: 'flex',
      gap: '8px',
      background: 'rgba(9, 23, 32, 0.94)',
      padding: '8px 14px',
      border: '1px solid #526c77',
      borderRadius: '6px',
      backdropFilter: 'blur(6px)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', marginRight: '12px', fontWeight: '800', color: '#8fc8da', fontSize: '14px', letterSpacing: '0.05em' }}>
        TWIN EARTH <span style={{ fontSize: '10px', color: '#a8c0ca', marginLeft: '6px', fontWeight: '400' }}>NASA Time Mirror</span>
      </div>
      
      {modes.map(m => (
        <button
          key={m.id}
          onClick={() => setMode(m.id)}
          style={{
            background: currentMode === m.id ? '#17374a' : 'transparent',
            color: currentMode === m.id ? '#fff' : '#a8c0ca',
            border: currentMode === m.id ? '1px solid #61afef' : '1px solid transparent',
            padding: '6px 12px',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: '700',
            fontSize: '12px',
            transition: 'all 0.2s'
          }}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}