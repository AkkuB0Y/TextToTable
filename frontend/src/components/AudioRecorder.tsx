import { useEffect, useRef } from 'react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';

interface AudioRecorderProps {
  onAudioReady: (blob: Blob) => void;
  isProcessing: boolean;
  size?: 'large' | 'small';
}

export function AudioRecorder({ onAudioReady, isProcessing, size = 'large' }: AudioRecorderProps) {
  const { isRecording, startRecording, stopRecording, analyserRef, error } = useAudioRecorder();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isRecording || !analyserRef.current || !canvasRef.current) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animationRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const barWidth = (canvas.width / bufferLength) * 2.5;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height;

        const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
        gradient.addColorStop(0, '#14b8a6');
        gradient.addColorStop(1, '#2dd4bf');

        ctx.fillStyle = gradient;
        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

        x += barWidth + 1;
      }
    };

    draw();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isRecording, analyserRef]);

  const handleClick = async () => {
    if (isProcessing) return;

    if (isRecording) {
      const blob = await stopRecording();
      if (blob) {
        onAudioReady(blob);
      }
    } else {
      startRecording();
    }
  };

  const isLarge = size === 'large';

  return (
    <div className={`flex flex-col items-center gap-6 ${isLarge ? '' : 'flex-row gap-3'}`}>
      <div className="relative flex flex-col items-center">
        <button
          onClick={handleClick}
          disabled={isProcessing}
          className={`mic-button ${isLarge ? 'mic-large' : 'mic-small'} ${isRecording ? 'recording' : ''} ${isProcessing ? 'processing' : ''}`}
          aria-label={isRecording ? 'Stop recording' : 'Start recording'}
        >
          {isProcessing ? (
            <svg className={`animate-spin text-white ${isLarge ? 'h-10 w-10' : 'h-5 w-5'}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          ) : isRecording ? (
            <svg className={`text-white ${isLarge ? 'w-10 h-10' : 'w-5 h-5'}`} fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg className={`text-white ${isLarge ? 'w-12 h-12' : 'w-6 h-6'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          )}
        </button>

        {/* Status text — only show in large mode */}
        {isLarge && (
          <div className="mt-6 text-center h-6">
            {error ? (
              <p className="text-red-400 text-sm font-medium">{error}</p>
            ) : isProcessing ? (
              <p className="text-neutral-400 text-sm font-medium animate-pulse">Processing...</p>
            ) : isRecording ? (
              <p className="text-red-400 text-sm font-bold tracking-widest animate-pulse">LISTENING...</p>
            ) : (
              <p className="text-neutral-500 text-sm font-medium tracking-wide">Tap to speak</p>
            )}
          </div>
        )}
      </div>

      {/* Waveform — only show in large mode */}
      {isLarge && (
        <div className={`waveform-container transition-opacity duration-300 ${isRecording ? 'opacity-100' : 'opacity-0'}`}>
          <canvas
            ref={canvasRef}
            width={280}
            height={56}
            className="w-full h-full"
          />
        </div>
      )}
    </div>
  );
}
