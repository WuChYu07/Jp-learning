---
name: Komorebi Design System
colors:
  surface: '#fff8f5'
  surface-dim: '#e9d6cc'
  surface-bright: '#fff8f5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#fff1ea'
  surface-container: '#feeadf'
  surface-container-high: '#f8e4da'
  surface-container-highest: '#f2dfd4'
  on-surface: '#231a13'
  on-surface-variant: '#564337'
  inverse-surface: '#392e27'
  inverse-on-surface: '#ffede4'
  outline: '#897365'
  outline-variant: '#dcc1b1'
  surface-tint: '#944a00'
  primary: '#944a00'
  on-primary: '#ffffff'
  primary-container: '#e67e22'
  on-primary-container: '#502600'
  inverse-primary: '#ffb783'
  secondary: '#3c6926'
  on-secondary: '#ffffff'
  secondary-container: '#b9ef9b'
  on-secondary-container: '#406e2a'
  tertiary: '#00658f'
  on-tertiary: '#ffffff'
  tertiary-container: '#00a3e4'
  on-tertiary-container: '#00354d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdcc5'
  primary-fixed-dim: '#ffb783'
  on-primary-fixed: '#301400'
  on-primary-fixed-variant: '#713700'
  secondary-fixed: '#bcf19d'
  secondary-fixed-dim: '#a1d584'
  on-secondary-fixed: '#072100'
  on-secondary-fixed-variant: '#25510f'
  tertiary-fixed: '#c7e7ff'
  tertiary-fixed-dim: '#86cfff'
  on-tertiary-fixed: '#001e2e'
  on-tertiary-fixed-variant: '#004c6d'
  background: '#fff8f5'
  on-background: '#231a13'
  surface-variant: '#f2dfd4'
typography:
  display-lg:
    fontFamily: Quicksand
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Quicksand
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  headline-md:
    fontFamily: Quicksand
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Noto Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Noto Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-caps:
    fontFamily: Quicksand
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  kanji-display:
    fontFamily: Noto Sans
    fontSize: 64px
    fontWeight: '500'
    lineHeight: 80px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1200px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  card-padding: 24px
---

## Brand & Style

The design system is built to facilitate a mindful and encouraging Japanese language learning experience. The brand personality is **warm, scholarly, and supportive**, aiming to reduce the cognitive load and "kanji-anxiety" often associated with language acquisition. 

The aesthetic blends **Soft Minimalism** with **Tactile** elements. It utilizes generous whitespace to mimic the intentionality of Japanese calligraphy while employing soft, organic shapes to remain approachable. The emotional goal is to evoke a sense of "Shoshin" (Beginner's Mind)—curiosity without intimidation. Surfaces should feel physical yet lightweight, utilizing subtle depth to guide the user's focus toward active learning modules and interactive exercises.

## Colors

The palette is inspired by natural Japanese elements: terracotta earth and matcha tea. 

- **Primary (#E67E22):** Used for primary actions, progress indicators, and highlighting active vocabulary. It provides the energy required for sustained study.
- **Secondary (#81B366):** Reserved for "Success" states, completed lesson markers, and correct answers in quizzes.
- **Background (#FCF8F3):** An off-white "Paper" tone that reduces blue-light strain during long reading sessions.
- **Neutrals:** We use a deep charcoal rather than pure black to maintain a softer contrast ratio, improving legibility for complex kanji characters. 

Apply the Seigaiha (wave) pattern as a low-opacity (#F2EBE3) watermark in header backgrounds or empty states to add cultural texture without distracting from content.

## Typography

This design system utilizes a dual-font strategy. **Quicksand** provides a friendly, rounded aesthetic for navigational elements, headings, and English labels. **Noto Sans** (specifically the JP variant) is used for all body text and Japanese characters to ensure maximum legibility and stroke clarity.

For grammar explanations, use `body-lg` to maintain a comfortable reading rhythm. The `kanji-display` role is specifically for flashcard fronts and character-drawing exercises, ensuring the user can see every stroke clearly.

## Layout & Spacing

The layout follows a **fluid grid system** with centered constraints for desktop viewing to prevent line lengths from becoming too long for educational reading. 

- **Mobile:** A 4-column grid with 16px side margins. Components should span the full width to maximize touch targets.
- **Tablet/Desktop:** A 12-column grid. Educational content (lessons) should be constrained to a 8-column central span (approx. 800px) to maintain focus.

Spacing is based on an 8px base unit. Use generous "Card-Padding" (24px) for learning modules to ensure that complex text doesn't feel cramped.

## Elevation & Depth

Hierarchy is established through **Tonal Layering** and **Soft Shadows**. 

1.  **Level 0 (Base):** The Cream background (#FCF8F3).
2.  **Level 1 (Cards):** Pure White (#FFFFFF) surfaces with a very soft, diffused shadow (12% opacity of the primary color or a warm gray). This creates a "lifted paper" effect.
3.  **Level 2 (Interactive):** Flashcards and active buttons use a slightly deeper shadow on hover to provide tactile feedback, mimicking a physical button being pressed.

Avoid harsh black shadows. Instead, use "Ambient Shadows"—tinted with a hint of the primary terracotta—to keep the interface feeling warm and integrated.

## Shapes

The shape language is defined by **High Circularity**. A standard radius of 16px (`rounded-lg`) is used for all primary containers and cards to reinforce the "friendly" brand pillar. 

- **Buttons:** Fully rounded (pill-shaped) to suggest interactivity.
- **Input Fields:** 12px radius to balance the softness of the cards while maintaining structure.
- **Progress Bars:** Fully rounded ends for a modern, fluid appearance.

## Components

### Buttons
Primary buttons use the Terracotta fill with white text. Secondary buttons use a thick 2px Matcha Green border with a transparent background. All buttons should have a minimum touch target of 48px.

### Interactive Flashcards
Flashcards are the core of the system. They must feature a 24px corner radius and a subtle "flip" animation. The "Pass" action uses a Matcha Green glow on hover, while the "Review Later" action uses a soft gray.

### Progress Bars
Progress bars should use a horizontal gradient from a lighter orange to the Primary Terracotta. The track should be a desaturated version of the background (#E0D7D0).

### Learning Modules (Cards)
Cards serve as the primary container for lessons. They must include a `label-caps` category tag at the top-left and use `gutter` (24px) internal padding to ensure grammar rules and kanji examples have breathing room.

### Feedback Toasts
Success messages use the Matcha Green palette. Error/Correction messages should use a soft Muted Red (#D63031) but maintain the same rounded shape language to avoid feeling overly punitive.