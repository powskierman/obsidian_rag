import React, { useState, useEffect } from 'react';

interface ThinkingIndicatorProps {
    searchMode: string;
    model: string;
    webSearchEnabled: boolean;
}

export const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({
    searchMode,
    model,
    webSearchEnabled
}) => {
    const [step, setStep] = useState(0);

    useEffect(() => {
        // Reset step when component mounts (thinking starts)
        setStep(0);

        const steps = [
            { id: 0, duration: 1500 }, // Initial search mode
            { id: 1, duration: 2500 }, // Model thinking
            { id: 2, duration: 2000 }, // Gathering knowledge
        ];

        if (webSearchEnabled) {
            steps.push({ id: 3, duration: 3000 }); // Web search (longer)
        }

        let currentStepIndex = 0;

        // Function to advance steps
        const advanceStep = () => {
            currentStepIndex++;
            if (currentStepIndex < steps.length) {
                setStep(currentStepIndex);
                timeoutId = setTimeout(advanceStep, steps[currentStepIndex].duration);
            }
        };

        // Start the sequence
        let timeoutId = setTimeout(advanceStep, steps[0].duration);

        return () => clearTimeout(timeoutId);
    }, [searchMode, model, webSearchEnabled]);

    const getMessage = () => {
        switch (step) {
            case 0:
                return `Performing ${searchMode} search...`;
            case 1:
                // Extract simplier model name for display
                const displayModel = model.includes('/') ? model.split('/')[1] : model;
                // Pretty print common models
                const prettyModel = displayModel.replace('claude-haiku-4.5', 'Claude 4.5 Haiku')
                    .replace('gemini-3-pro-preview', 'Gemini 3 Pro')
                    .replace('claude-3-5-sonnet', 'Claude 3.5 Sonnet');
                return `💭 Thinking with ${prettyModel}...`;
            case 2:
                return "🧠 Gathering additional knowledge...";
            case 3:
                return "🌐 Searching the web...";
            default:
                return "Generating response...";
        }
    };

    return (
        <div className="thinking-indicator-detailed">
            <span className="thinking-spinner">⚡</span>
            <span className="thinking-text">{getMessage()}</span>
            <style jsx>{`
        .thinking-indicator-detailed {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          color: rgba(255, 255, 255, 0.8);
          font-size: 0.9rem;
          font-weight: 500;
          animation: fadeIn 0.3s ease-in-out;
        }
        .thinking-spinner {
          animation: pulse 1s infinite alternate;
          filter: drop-shadow(0 0 5px var(--neon-blue));
        }
        .thinking-text {
          background: linear-gradient(90deg, #fff 0%, #aaa 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        @keyframes pulse {
          from { opacity: 0.5; transform: scale(0.9); }
          to { opacity: 1; transform: scale(1.1); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(5px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
        </div>
    );
};
