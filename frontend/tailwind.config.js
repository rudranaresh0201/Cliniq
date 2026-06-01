// =============================================================================
//  ClinIQ 2.0 — Tailwind Configuration
//  Typography system built as a named-token plugin.
//
//  Every font-size, weight, tracking, and leading step lives here as a
//  Tailwind token — no magic numbers ever need to appear in component code.
//
//  Utility classes generated:
//    text-{hero|display|title|heading|body-lg|body|small|caption}
//    text-{mono-hero|mono-lg|mono-md|mono-sm}
//    font-inter | font-mono
//    tracking-{display|title|heading|snug|body|wide-sm|caption}
//    leading-{hero|display|title|heading|body-lg|body|small|caption}
//
//  Component classes (injected via plugin into @layer components):
//    .typo-hero | .typo-display | .typo-heading | .typo-body
//    .typo-caption | .typo-value | .typo-label
// =============================================================================

import plugin from 'tailwindcss/plugin';

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],

  theme: {
    extend: {

      // ── Font families ───────────────────────────────────────────────────
      //    font-inter  →  all UI text
      //    font-mono   →  ALL numeric values, lab results, scores
      fontFamily: {
        sans:  ['Inter Variable', 'Inter', 'system-ui', 'sans-serif'],
        inter: ['Inter Variable', 'Inter', 'system-ui', 'sans-serif'],
        mono:  ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
      },

      // ── Type scale ──────────────────────────────────────────────────────
      //    Format: [fontSize, { lineHeight, letterSpacing, fontWeight }]
      //    Tailwind merges these into a single text-{key} utility that sets
      //    all four properties simultaneously.
      fontSize: {

        // ── UI text scale ──────────────────────────────────────────────
        'hero': [
          'clamp(56px, 8vw, 80px)',
          { lineHeight: '1.1',  letterSpacing: '-3px',   fontWeight: '700' },
        ],
        'display': [
          'clamp(32px, 5vw, 48px)',
          { lineHeight: '1.15', letterSpacing: '-2px',   fontWeight: '600' },
        ],
        'title': [
          '28px',
          { lineHeight: '1.3',  letterSpacing: '-1px',   fontWeight: '600' },
        ],
        'heading': [
          '20px',
          { lineHeight: '1.4',  letterSpacing: '-0.5px', fontWeight: '600' },
        ],
        'body-lg': [
          '17px',
          { lineHeight: '1.7',  letterSpacing: '0px',    fontWeight: '400' },
        ],
        'body': [
          '15px',
          { lineHeight: '1.6',  letterSpacing: '0px',    fontWeight: '400' },
        ],
        'small': [
          '13px',
          { lineHeight: '1.5',  letterSpacing: '0.1px',  fontWeight: '400' },
        ],
        'caption': [
          '11px',
          { lineHeight: '1.4',  letterSpacing: '0.5px',  fontWeight: '500' },
        ],

        // ── Mono scale (JetBrains Mono — lab values only) ──────────────
        'mono-hero': [
          '48px',
          { lineHeight: '1.1',  letterSpacing: '-1px',   fontWeight: '700' },
        ],
        'mono-lg': [
          '20px',
          { lineHeight: '1.4',  letterSpacing: '-0.3px', fontWeight: '500' },
        ],
        'mono-md': [
          '15px',
          { lineHeight: '1.5',  letterSpacing: '0px',    fontWeight: '400' },
        ],
        'mono-sm': [
          '13px',
          { lineHeight: '1.5',  letterSpacing: '0px',    fontWeight: '400' },
        ],
      },

      // ── Letter-spacing ──────────────────────────────────────────────────
      //    Named tokens — use tracking-{key} in component code.
      letterSpacing: {
        'display':  '-3px',   // hero headings
        'title':    '-2px',   // display headings
        'heading':  '-1px',   // section titles
        'snug':     '-0.5px', // subheadings
        'body':     '0px',    // body copy
        'wide-sm':  '0.1px',  // small text
        'caption':  '0.5px',  // captions, labels (often paired with uppercase)
        'mono-val': '-1px',   // mono hero numbers
      },

      // ── Line-heights ────────────────────────────────────────────────────
      //    Named tokens — use leading-{key} in component code.
      lineHeight: {
        'hero':     '1.1',
        'display':  '1.15',
        'title':    '1.3',
        'heading':  '1.4',
        'body-lg':  '1.7',
        'body':     '1.6',
        'small':    '1.5',
        'caption':  '1.4',
      },

      // ── Font weights ────────────────────────────────────────────────────
      //    Only additions not already in Tailwind's defaults (100–900).
      //    Tailwind ships: thin=100 extralight=200 light=300 normal=400
      //                    medium=500 semibold=600 bold=700 extrabold=800
      //                    black=900
      //    All spec weights are already covered; nothing to add here.

    },
  },

  plugins: [

    plugin(function typographyPlugin({ addBase, addComponents, addUtilities, theme }) {
      const fonts = (key) => { const v = theme(key); return Array.isArray(v) ? v.join(', ') : String(v); };

      // ── Base layer ──────────────────────────────────────────────────────
      //    Sets root font behaviour. Deliberately avoids overriding color so
      //    index.css retains control of the initial text color.
      addBase({

        'html': {
          fontSize:            '16px',
          fontOpticalSizing:   'auto',
        },

        'body': {
          fontFamily:                fonts('fontFamily.inter'),
          fontFeatureSettings:       '"cv01" 1, "cv02" 1, "ss01" 1, "ss03" 1',
          fontOpticalSizing:         'auto',
          WebkitFontSmoothing:       'antialiased',
          MozOsxFontSmoothing:       'grayscale',
          textRendering:             'optimizeLegibility',
        },

        // Mono elements always render with JetBrains Mono
        'code, kbd, samp, pre': {
          fontFamily:          fonts('fontFamily.mono'),
          fontFeatureSettings: '"liga" 0, "zero" 1',
          fontVariantNumeric:  'tabular-nums',
        },

        // Selection tint — violet-branded
        '::selection': {
          backgroundColor: 'rgba(124, 101, 246, 0.25)',
          color:           'var(--text-primary, #F0F0F4)',
        },

        // Heading reset — optical sizing by default
        'h1, h2, h3, h4, h5, h6': {
          fontOpticalSizing:   'auto',
          fontFeatureSettings: '"cv01" 1, "cv02" 1',
        },

      });


      // ── Component variants — .typo-{variant} ────────────────────────────
      //    These are the Typography component's CSS primitives.
      //    Each maps to one row in the type scale spec.
      //    Because these live in @layer components, any Tailwind utility
      //    applied alongside (e.g. "typo-body text-white") wins correctly.
      addComponents({

        // hero — large page titles; gradient text is opt-in via .gradient-text
        '.typo-hero': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      'clamp(56px, 8vw, 80px)',
          fontWeight:    '700',
          letterSpacing: '-3px',
          lineHeight:    '1.1',
          fontOpticalSizing: 'auto',
          // Default: gradient text treatment for the hero variant
          background:              'linear-gradient(135deg, var(--text-primary, #F0F0F4) 0%, var(--text-accent, #9B87FF) 100%)',
          WebkitBackgroundClip:    'text',
          WebkitTextFillColor:     'transparent',
          backgroundClip:          'text',
          // Fallback color for browsers that don't support background-clip: text
          color:                   'var(--text-primary, #F0F0F4)',
        },

        // display — section openers, modal titles
        '.typo-display': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      'clamp(32px, 5vw, 48px)',
          fontWeight:    '600',
          letterSpacing: '-2px',
          lineHeight:    '1.15',
          color:         'var(--text-primary, #F0F0F4)',
        },

        // title — card headers, panel titles (28px)
        '.typo-title': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      '28px',
          fontWeight:    '600',
          letterSpacing: '-1px',
          lineHeight:    '1.3',
          color:         'var(--text-primary, #F0F0F4)',
        },

        // heading — within-card section labels (20px)
        '.typo-heading': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      '20px',
          fontWeight:    '600',
          letterSpacing: '-0.5px',
          lineHeight:    '1.4',
          color:         'var(--text-primary, #F0F0F4)',
        },

        // body — default reading text; secondary color
        '.typo-body': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      '15px',
          fontWeight:    '400',
          letterSpacing: '0px',
          lineHeight:    '1.6',
          color:         'var(--text-secondary, #8B8B99)',
        },

        // body-lg — narrative clinical summaries
        '.typo-body-lg': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      '17px',
          fontWeight:    '400',
          letterSpacing: '0px',
          lineHeight:    '1.7',
          color:         'var(--text-secondary, #8B8B99)',
        },

        // caption — supporting metadata; muted + uppercase
        '.typo-caption': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      '11px',
          fontWeight:    '500',
          letterSpacing: '0.5px',
          lineHeight:    '1.4',
          textTransform: 'uppercase',
          color:         'var(--text-muted, #4A4A5A)',
        },

        // value — JetBrains Mono; ALL numeric lab results, scores, dosages
        //         tabular-nums keeps columns aligned; slashed zero avoids 0/O confusion
        '.typo-value': {
          fontFamily:          fonts('fontFamily.mono'),
          fontSize:            '15px',
          fontWeight:          '400',
          letterSpacing:       '0px',
          lineHeight:          '1.5',
          fontVariantNumeric:  'tabular-nums',
          fontFeatureSettings: '"liga" 0, "zero" 1',
          WebkitFontSmoothing: 'subpixel-antialiased',
          color:               'var(--text-primary, #F0F0F4)',
        },

        // value-lg — larger mono readings (risk scores, main metric display)
        '.typo-value-lg': {
          fontFamily:          fonts('fontFamily.mono'),
          fontSize:            '20px',
          fontWeight:          '500',
          letterSpacing:       '-0.3px',
          lineHeight:          '1.4',
          fontVariantNumeric:  'tabular-nums',
          fontFeatureSettings: '"liga" 0, "zero" 1',
          WebkitFontSmoothing: 'subpixel-antialiased',
          color:               'var(--text-primary, #F0F0F4)',
        },

        // value-hero — mono hero number treatment (patient risk score, eGFR, etc.)
        '.typo-value-hero': {
          fontFamily:          fonts('fontFamily.mono'),
          fontSize:            '48px',
          fontWeight:          '700',
          letterSpacing:       '-1px',
          lineHeight:          '1.1',
          fontVariantNumeric:  'tabular-nums',
          fontFeatureSettings: '"liga" 0, "zero" 1',
          WebkitFontSmoothing: 'subpixel-antialiased',
          color:               'var(--text-primary, #F0F0F4)',
        },

        // label — field names, form labels; muted, no uppercase
        '.typo-label': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      '11px',
          fontWeight:    '500',
          letterSpacing: '0.5px',
          lineHeight:    '1.4',
          color:         'var(--text-muted, #4A4A5A)',
        },

        // small — secondary metadata, timestamps
        '.typo-small': {
          fontFamily:    fonts('fontFamily.inter'),
          fontSize:      '13px',
          fontWeight:    '400',
          letterSpacing: '0.1px',
          lineHeight:    '1.5',
          color:         'var(--text-secondary, #8B8B99)',
        },

      });


      // ── Utilities ────────────────────────────────────────────────────────
      addUtilities({

        // Gradient text — hero numbers and accent highlights
        '.gradient-text': {
          background:              'linear-gradient(135deg, var(--text-primary, #F0F0F4) 0%, var(--text-accent, #9B87FF) 100%)',
          WebkitBackgroundClip:    'text',
          WebkitTextFillColor:     'transparent',
          backgroundClip:          'text',
          color:                   'var(--text-primary, #F0F0F4)',
        },

        // Semantic gradient text variants
        '.gradient-text-critical': {
          background:              'linear-gradient(135deg, #FF6B6B 0%, var(--critical, #FF4444) 100%)',
          WebkitBackgroundClip:    'text',
          WebkitTextFillColor:     'transparent',
          backgroundClip:          'text',
          color:                   'var(--critical, #FF4444)',
        },

        '.gradient-text-stable': {
          background:              'linear-gradient(135deg, #4ADE80 0%, var(--stable, #22C55E) 100%)',
          WebkitBackgroundClip:    'text',
          WebkitTextFillColor:     'transparent',
          backgroundClip:          'text',
          color:                   'var(--stable, #22C55E)',
        },

        // Tabular numerics shorthand — for any element rendering aligned numbers
        '.tabular': {
          fontVariantNumeric:  'tabular-nums',
          fontFeatureSettings: '"tnum" 1',
        },

        // Slashed zero — for security codes, patient IDs, lab accession numbers
        '.slashed-zero': {
          fontFeatureSettings: '"zero" 1',
        },

        // Font smoothing
        '.smooth-antialiased': {
          WebkitFontSmoothing: 'antialiased',
          MozOsxFontSmoothing: 'grayscale',
        },

        '.smooth-subpixel': {
          WebkitFontSmoothing: 'subpixel-antialiased',
          MozOsxFontSmoothing: 'auto',
        },

      });

    }),

  ],

};
