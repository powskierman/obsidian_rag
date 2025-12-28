import React, { useState } from 'react';
import { api } from '../../lib/api';

interface RatingButtonsProps {
  queryId: string;
  query: string;
  searchMode: string;
  model: string;
  onRated?: (rating: number) => void;
  initialRating?: number;
}

const ratings = [
  { value: 1, emoji: '😞', label: '1' },
  { value: 2, emoji: '😕', label: '2' },
  { value: 3, emoji: '😐', label: '3' },
  { value: 4, emoji: '😊', label: '4' },
  { value: 5, emoji: '😍', label: '5' },
];

export default function RatingButtons({
  queryId,
  query,
  searchMode,
  model,
  onRated,
  initialRating,
}: RatingButtonsProps) {
  const [rating, setRating] = useState<number | null>(initialRating || null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRate = async (value: number) => {
    if (rating !== null) return; // Already rated

    setIsSubmitting(true);
    setRating(value);

    try {
      await api.submitFeedback({
        query_id: queryId,
        rating: value,
        query,
        search_mode: searchMode,
        model,
        timestamp: new Date().toISOString(),
      });

      if (onRated) {
        onRated(value);
      }
    } catch (error) {
      console.error('Failed to submit rating:', error);
      setRating(null); // Reset on error
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-4 pt-4 border-t border-[#2C2C2E]">
      <div className="text-xs text-white/60 mb-2">Rate this response:</div>

      {rating === null ? (
        <div className="flex gap-2">
          {ratings.map((r) => (
            <button
              key={r.value}
              onClick={() => handleRate(r.value)}
              disabled={isSubmitting}
              className="flex-1 flex flex-col items-center gap-1 p-2 rounded-lg bg-[#1C1C1E] hover:bg-[#2C2C2E] border border-[#2C2C2E] transition-colors disabled:opacity-50"
              title={`Rate ${r.value} stars`}
            >
              <span className="text-xl">{r.emoji}</span>
              <span className="text-[10px] text-white/40">{r.label}</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-2 text-sm text-white/60">
          <span>Already rated:</span>
          <div className="flex items-center gap-1">
            {ratings.slice(0, rating).map((r) => (
              <span key={r.value} className="text-base">
                ⭐
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
