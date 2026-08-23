import { useState, useEffect } from 'react';

function App() {
  const [status, setStatus] = useState('checking...');
  const [error, setError] = useState(null);

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';

    fetch(`${apiUrl}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`Server responded with ${res.status}`);
        return res.json();
      })
      .then((data) => setStatus(data.status))
      .catch((err) => {
        console.error('Health check failed:', err);
        setError(err.message);
        setStatus('unreachable');
      });
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center justify-center gap-4">
      <h1 className="text-3xl font-bold tracking-tight">FraudRing</h1>
      <p className="text-slate-400">AI-powered coordinated fraud &amp; abuse intelligence platform</p>
      <div className="mt-6 px-4 py-2 rounded-lg border border-slate-700 bg-slate-800">
        <span className="text-sm text-slate-400">Backend status: </span>
        <span className={status === 'ok' ? 'text-emerald-400 font-semibold' : 'text-red-400 font-semibold'}>
          {status}
        </span>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}

export default App;