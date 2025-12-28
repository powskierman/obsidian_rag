import { NextResponse } from 'next/server';

export async function GET() {
  const apiKeys = {
    gemini: !!process.env.GEMINI_API_KEY,
    anthropic: !!process.env.ANTHROPIC_API_KEY,
  };

  return NextResponse.json(apiKeys);
}
