// Central environment and API configuration
// Ensures 100% backward compatibility with packaged Windows Electron executables
// and the web cloud runtime in AI Studio.

export const isElectron = typeof window !== 'undefined' && (
  window.location.protocol === 'file:' ||
  Boolean(window.navigator?.userAgent?.includes('Electron')) ||
  Boolean(window.electronAPI && window.electronAPI.isElectron)
);

// Desktop Electron loads UI via file:///... and talks to local Python FastAPI backend at 127.0.0.1:8765.
// Web AI Studio loads UI via http://... on port 3000 and talks to server.ts via relative '/api' routes.
export const API_BASE = isElectron ? 'http://127.0.0.1:8765' : '';

export const getApiUrl = (endpoint) => {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${API_BASE}${cleanEndpoint}`;
};
