import { AudioRecorder } from './components/AudioRecorder';
import { useQueryStream } from './hooks/useQueryStream';

function App() {
  const { isProcessing, response, error, sendQuery } = useQueryStream();

  const handleAudioReady = (blob: Blob) => {
    sendQuery(blob);
  };

  return (
    <>
      {/* Background decoration */}
      <div className="bg-orb bg-orb-1" />
      <div className="bg-orb bg-orb-2" />

      <main className="w-full max-w-4xl mx-auto px-6 py-12 flex flex-col items-center min-h-screen">
        
        {/* Header */}
        <header className="text-center mb-16 animate-fade-in-up">
          <div className="inline-flex items-center justify-center p-3 mb-6 rounded-2xl glass-subtle shadow-xl">
            <svg className="w-8 h-8 text-accent-secondary mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span className="text-xl font-bold tracking-wider text-slate-200">Texto<span className="text-accent-glow">Analytics</span></span>
          </div>
          <h1 className="text-5xl font-extrabold mb-4 tracking-tight title-gradient">
            Speak to your data.
          </h1>
          <p className="text-lg text-slate-400 max-w-lg mx-auto">
            Ask questions in plain English and get instant, interactive dashboards powered by AI.
          </p>
        </header>

        {/* Main interactive area */}
        <div className="w-full max-w-2xl glass shadow-2xl p-8 mb-12 animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
          <AudioRecorder 
            onAudioReady={handleAudioReady} 
            isProcessing={isProcessing} 
          />
        </div>

        {/* Phase 2: Stub Response Area */}
        <div className="w-full max-w-2xl animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
          {error && (
            <div className="p-4 rounded-xl bg-red-900/40 border border-red-500/30 text-red-200 mb-6">
              <div className="flex items-center">
                <svg className="w-5 h-5 mr-3 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                {error}
              </div>
            </div>
          )}

          {response && (
            <div className="glass-subtle p-6 rounded-xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-accent-glow">Backend Response (Phase 1 Stub)</h3>
                <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-medium border border-emerald-500/30">
                  Success
                </span>
              </div>
              <div className="bg-[#0a0a1a] rounded-lg p-4 border border-slate-800">
                <pre className="text-sm text-slate-300 response-area font-mono">
                  {JSON.stringify(response, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>

      </main>
    </>
  );
}

export default App;
