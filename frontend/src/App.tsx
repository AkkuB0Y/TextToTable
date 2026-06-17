import { AudioRecorder } from './components/AudioRecorder';
import { useQueryStream } from './hooks/useQueryStream';

function App() {
  const { isProcessing, response, error, sendQuery, reset } = useQueryStream();

  const handleAudioReady = (blob: Blob) => {
    sendQuery(blob);
  };

  const hasResults = !!(response || error);

  return (
    <>
      {hasResults ? (
        /* ── Active layout: mic in top-right, results below ── */
        <main className="layout-active">
          <div className="top-bar">
            <div className="flex items-center gap-3">
              <button 
                onClick={reset}
                className="text-lg font-semibold tracking-wide text-white py-3 hover:opacity-80 transition-opacity cursor-pointer focus:outline-none"
              >
                TextTo<span className="text-accent-primary">Table</span>
              </button>
            </div>
            <AudioRecorder
              onAudioReady={handleAudioReady}
              isProcessing={isProcessing}
              size="small"
            />
          </div>

          <div className="results-area w-full max-w-3xl mx-auto">
            {error && (
              <div className="p-4 rounded-xl bg-red-950/50 border border-red-500/20 text-red-300 mb-6">
                <div className="flex items-center gap-3">
                  <svg className="w-5 h-5 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>{error}</span>
                </div>
              </div>
            )}

            {response && (
              <div className="flex flex-col gap-6">
                {/* Transcript Bubble */}
                <div className="flex flex-col items-center mb-4 animate-fade-in-up">
                  <span className="text-xs text-neutral-500 uppercase tracking-widest mb-2 font-medium">You asked</span>
                  <div className="px-6 py-3 rounded-2xl bg-neutral-900 border border-neutral-800 shadow-lg">
                    <p className="text-xl font-medium text-white tracking-wide">
                      "{response.transcript || 'No transcript available'}"
                    </p>
                  </div>
                </div>

                <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-8 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-lg font-medium text-accent-glow">Backend Response</h3>
                    <span className="px-4 py-1.5 rounded-full bg-teal-500/10 text-teal-400 text-sm font-medium border border-teal-500/20">
                      Success
                    </span>
                  </div>
                  <div className="bg-black rounded-lg p-4 border border-neutral-800">
                    <pre className="text-sm text-neutral-300 response-area font-mono whitespace-pre-wrap">
                      {JSON.stringify(response, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      ) : (
        /* ── Centered layout: mic is the hero ── */
        <main className="layout-centered">
          <div className="flex flex-col items-center gap-3 mb-20 animate-fade-in-up">
            <span className="text-2xl font-bold tracking-wide text-white">
              TextTo<span className="text-accent-primary">Table</span>
            </span>
            <p className="text-sm text-neutral-500">
              Ask questions about your data in plain English.
            </p>
          </div>

          <AudioRecorder
            onAudioReady={handleAudioReady}
            isProcessing={isProcessing}
            size="large"
          />
        </main>
      )}
    </>
  );
}

export default App;
