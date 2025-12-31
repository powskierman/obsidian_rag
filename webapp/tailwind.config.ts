import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Custom colors matching the new aesthetic
        'glass-bg': 'rgba(255, 255, 255, 0.05)', // Very subtle white tint
        'glass-border': 'rgba(255, 255, 255, 0.1)',
        'accent-purple': '#a855f7', // Matches the glowing network
        'accent-purple-hover': '#9333ea',
        'accent-gold': '#fbbf24', // Matches the banana and active 'Hybrid' button
        'accent-gold-hover': '#f59e0b',
      },
      backdropBlur: {
        'xs': '2px',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic':
          'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
export default config
