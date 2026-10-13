/**
 * The look of the app. Importing this module loads the fonts, the tokens and the page-wide styles.
 * To change the look, replace this folder and keep exporting the same names.
 */
import './fonts.css'
import './tokens.css'
import './base.css'
import './prose.css'

/** How Clerk's sign-in form is dressed; it reads the same tokens as everything else. */
export const clerkAppearance = {
  variables: {
    colorPrimary: 'var(--accent)',
    colorBackground: 'var(--paper)',
    colorText: 'var(--ink)',
    colorTextSecondary: 'var(--ink-muted)',
    colorInputBackground: 'var(--field)',
    colorInputText: 'var(--ink)',
    fontFamily: 'var(--font-manuscript)',
    borderRadius: 'var(--radius-paper)',
  },
} as const
