# KEN-E Design System — "Soft Maximalism"

> **Version:** 2.0.0 - Rebalanced
> **Last Updated:** 2026-02-14
> **Design Philosophy:** Joyful sophistication through controlled visual abundance. Every element earns its place — color is generous but harmonious, motion is playful but purposeful, and personality never compromises usability.
> **Target Audience:** Marketing professionals who want powerful AI-native tools that feel warm, inviting, and fun to use — with a balanced, professional aesthetic.
> **Accessibility Target:** WCAG AAA compliance (7:1 contrast ratio for normal text, 4.5:1 for large text)
> 
> **Note:** Version 2.0 represents a comprehensive rebalance from the initial design. The palette has shifted to cooler tones (blues, slate, deep purples, teal, amber) for a more professional feel, typography has been unified to Plus Jakarta Sans throughout, border radii have been moderated, and animations refined for subtlety while preserving the signature playful rotations and rainbow gradients.

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Color Palette](#2-color-palette)
3. [Typography](#3-typography)
4. [Spacing & Layout](#4-spacing--layout)
5. [Elevation & Depth](#5-elevation--depth)
6. [Border & Radius](#6-border--radius)
7. [Animations & Motion](#7-animations--motion)
8. [Component Guidelines](#8-component-guidelines)
9. [Chat Interface Components](#9-chat-interface-components)
10. [Form Elements](#10-form-elements)
11. [Data Visualization](#11-data-visualization)
12. [Iconography](#12-iconography)
13. [CSS Custom Properties](#13-css-custom-properties)
14. [Figma Implementation Notes](#14-figma-implementation-notes)

---

## 1. Design Principles

### The Five Pillars of KEN-E Design

1. **Joyful First** — Every interaction should spark a small moment of delight. Color, motion, and personality are features, not decoration.
2. **Controlled Abundance** — Maximalism with discipline. Every visual element has a purpose. More is more, but only when each addition earns its place.
3. **Warm Intelligence** — AI-native technology should feel approachable, not intimidating. Sophisticated capability wrapped in human warmth.
4. **Playful Precision** — Micro-rotations, bouncy animations, and colorful accents coexist with rigorous alignment, consistent spacing, and clear hierarchy.
5. **Inclusive by Default** — WCAG AAA compliance is non-negotiable. Accessibility and beauty are not in tension.

### What Makes KEN-E Unforgettable

- **The slight rotation** — Cards, buttons, and badges tilt 0.5–2° on hover, creating a handcrafted, "pinned to a board" feeling
- **Rainbow gradient borders** — The signature multi-color gradient stripe appears on key structural elements (nav borders, dividers, progress indicators)
- **Color-coded left borders** — Integration cards and list items get a unique accent color, creating a visual "filing system"
- **Background blobs** — Soft, blurred color shapes in the background create atmosphere and depth without competing with content
- **Grain texture overlay** — A subtle noise texture over the entire viewport adds tactile warmth

---

## 2. Color Palette

### 2.1 Core Brand Colors (Rebalanced v2.0)

| Token Name | Light Mode | Dark Mode | Usage |
|---|---|---|---|
| `slate` | `#64748B` | `#94A3B8` | Neutral accents, professional tone |
| `blue` | `#3B82F6` | `#60A5FA` | Primary interactive, trust, professionalism |
| `violet` | `#6366F1` | `#818CF8` | Primary CTAs, links, focus states |
| `teal` | `#2EC4B6` | `#40D6C8` | Success, active states, positive actions |
| `amber` | `#F59E0B` | `#FBBF24` | Highlights, warnings, energy accents |

**Design Note:** The v2.0 color palette replaces the original warm coral/pink-dominant scheme with cooler blues, slate, and deep purples to achieve a more balanced, professional aesthetic while maintaining joyful personality.

### 2.2 Extended Color Scales

Each core color has a 5-step scale from soft to full:

#### Slate Scale
| Token | Light Mode | Dark Mode |
|---|---|---|
| `slate-100` | `#F1F5F9` | `#1E293B` |
| `slate-200` | `#E2E8F0` | `#334155` |
| `slate-300` | `#CBD5E1` | `#475569` |
| `slate-400` | `#94A3B8` | `#64748B` |
| `slate-500` | `#64748B` | `#94A3B8` |

#### Blue Scale
| Token | Light Mode | Dark Mode |
|---|---|---|
| `blue-100` | `#EFF6FF` | `#1E3A8A` |
| `blue-200` | `#DBEAFE` | `#1E40AF` |
| `blue-300` | `#BFDBFE` | `#2563EB` |
| `blue-400` | `#60A5FA` | `#3B82F6` |
| `blue-500` | `#3B82F6` | `#60A5FA` |

#### Violet Scale
| Token | Light Mode | Dark Mode |
|---|---|---|
| `violet-100` | `#EEF2FF` | `#312E81` |
| `violet-200` | `#E0E7FF` | `#3730A3` |
| `violet-300` | `#C7D2FE` | `#4F46E5` |
| `violet-400` | `#818CF8` | `#6366F1` |
| `violet-500` | `#6366F1` | `#818CF8` |

#### Teal Scale
| Token | Light Mode | Dark Mode |
|---|---|---|
| `teal-100` | `#E8F8F6` | `#132D2A` |
| `teal-200` | `#C4EDE8` | `#1E4A44` |
| `teal-300` | `#A8E6E0` | `#2A6B62` |
| `teal-400` | `#6AD8CC` | `#36A898` |
| `teal-500` | `#2EC4B6` | `#40D6C8` |

#### Amber Scale
| Token | Light Mode | Dark Mode |
|---|---|---|
| `amber-100` | `#FEF3C7` | `#78350F` |
| `amber-200` | `#FDE68A` | `#92400E` |
| `amber-300` | `#FCD34D` | `#B45309` |
| `amber-400` | `#FBBF24` | `#F59E0B` |
| `amber-500` | `#F59E0B` | `#FBBF24` |

### 2.3 Neutral / Surface Colors

| Token | Light Mode | Dark Mode | Usage |
|---|---|---|---|
| `bg-primary` | `#FAFBFC` | `#0F172A` | Page background |
| `bg-secondary` | `#F3F4F6` | `#1E293B` | Alternate/section bg |
| `bg-elevated` | `#FFFFFF` | `#1E293B` | Cards, modals, popovers |
| `bg-overlay` | `rgba(30,41,59,0.5)` | `rgba(0,0,0,0.7)` | Modal/drawer overlays |
| `surface-muted` | `#F8F9FA` | `#334155` | Disabled states, subtle bg |
| `text-primary` | `#1E293B` | `#F1F5F9` | Headings, body text |
| `text-secondary` | `#475569` | `#CBD5E1` | Supporting text |
| `text-tertiary` | `#94A3B8` | `#94A3B8` | Captions, timestamps |
| `text-disabled` | `#CBD5E1` | `#475569` | Disabled labels |
| `text-inverse` | `#FFFFFF` | `#0F172A` | Text on colored backgrounds |
| `border-default` | `#E2E8F0` | `#334155` | Card/input borders |
| `border-subtle` | `#F1F5F9` | `#1E293B` | Dividers, separators |
| `border-strong` | `#CBD5E1` | `#475569` | Emphasized borders |

### 2.4 Semantic Colors

| Token | Light Mode | Dark Mode | Usage |
|---|---|---|---|
| `success` | `#10B981` | `#34D399` | Connected, complete, positive |
| `success-bg` | `#D1FAE5` | `#064E3B` | Success background fill |
| `success-text` | `#065F46` | `#34D399` | Success text (AAA on bg) |
| `error` | `#EF4444` | `#F87171` | Error, failed, destructive |
| `error-bg` | `#FEE2E2` | `#7F1D1D` | Error background fill |
| `error-text` | `#991B1B` | `#F87171` | Error text (AAA on bg) |
| `warning` | `#F59E0B` | `#FBBF24` | Caution, pending |
| `warning-bg` | `#FEF3C7` | `#78350F` | Warning background fill |
| `warning-text` | `#92400E` | `#FBBF24` | Warning text (AAA on bg) |
| `info` | `#6366F1` | `#818CF8` | Informational, neutral |
| `info-bg` | `#EEF2FF` | `#312E81` | Info background fill |
| `info-text` | `#3730A3` | `#818CF8` | Info text (AAA on bg) |
| `disconnected` | `#94A3B8` | `#64748B` | Inactive, offline |
| `disconnected-bg` | `#F1F5F9` | `#1E293B` | Disconnected bg fill |

### 2.5 Special Effect Colors

| Token | Light Mode | Dark Mode | Usage |
|---|---|---|---|
| `gradient-rainbow` | `linear-gradient(90deg, #3B82F6, #6366F1, #2EC4B6, #F59E0B)` | `linear-gradient(90deg, #60A5FA, #818CF8, #40D6C8, #FBBF24)` | Signature border/divider |
| `gradient-cta` | `linear-gradient(135deg, #3B82F6, #6366F1)` | `linear-gradient(135deg, #60A5FA, #818CF8)` | Primary CTA buttons |
| `gradient-subtle` | `linear-gradient(135deg, #A8E6E0, #C7D2FE)` | `linear-gradient(135deg, #2A6B62, #4F46E5)` | Icon backgrounds, accents |
| `blob-blue` | `rgba(59,130,246,0.08)` | `rgba(59,130,246,0.05)` | Background blob |
| `blob-violet` | `rgba(99,102,241,0.08)` | `rgba(99,102,241,0.05)` | Background blob |
| `blob-teal` | `rgba(46,196,182,0.08)` | `rgba(46,196,182,0.05)` | Background blob |
| `blob-slate` | `rgba(100,116,139,0.05)` | `rgba(100,116,139,0.03)` | Background blob |
| `grain-opacity` | `0.02` | `0.04` | Noise texture overlay |

### 2.6 Card Accent Colors (Left Border)

Cards in lists/grids cycle through these accent colors in order:

| Position | Token | Light Mode | Dark Mode |
|---|---|---|---|
| 1st | `accent-slot-1` | `#6366F1` (violet) | `#818CF8` |
| 2nd | `accent-slot-2` | `#3B82F6` (blue) | `#60A5FA` |
| 3rd | `accent-slot-3` | `#2EC4B6` (teal) | `#40D6C8` |
| 4th | `accent-slot-4` | `#F59E0B` (amber) | `#FBBF24` |
| 5th | `accent-slot-5` | `#6366F1` (violet) | `#818CF8` |
| 6th | `accent-slot-6` | `#3B82F6` (blue) | `#60A5FA` |

Cycle restarts at position 7. The pattern is: violet → blue → teal → amber → violet → blue.

### 2.7 AAA Contrast Verification Notes

All text-on-background combinations must meet these minimums:

| Combination | Required Ratio | Target |
|---|---|---|
| `text-primary` on `bg-primary` | 7:1 | Body text, headings |
| `text-primary` on `bg-elevated` | 7:1 | Card text |
| `text-secondary` on `bg-primary` | 7:1 | Supporting text |
| `text-tertiary` on `bg-primary` | 4.5:1 | Large text only (18px+) |
| `text-inverse` on `violet-500` | 7:1 | Button labels |
| `text-inverse` on `teal-500` | 7:1 | Active tab labels |
| `success-text` on `success-bg` | 7:1 | Status badges |
| `error-text` on `error-bg` | 7:1 | Error badges |

> **Figma Note:** Use the "Stark" or "A11y - Color Contrast Checker" plugin to verify all combinations before handoff. Flag any combination below 7:1 for normal text.

---

## 3. Typography

### 3.1 Font Families (Unified in v2.0)

| Token | Font | Weight Range | Usage |
|---|---|---|---|
| `font-display` | **Plus Jakarta Sans** | 400–800 | Headings, hero text, card titles, all display text |
| `font-body` | **Plus Jakarta Sans** | 400–700 | Body text, labels, UI elements, form inputs |

**Design Note:** Version 2.0 unifies the typography system to use Plus Jakarta Sans throughout the entire application. This creates a more cohesive, professional aesthetic while maintaining excellent readability. The original design used Fraunces for headings, but this has been replaced with Plus Jakarta Sans at appropriate weights.

**Loading strategy:** Font loaded from Google Fonts. Use `font-display: swap` for performance. System fallback: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` for Plus Jakarta Sans.

### 3.2 Type Scale

| Token | Size | Line Height | Weight | Font | Usage |
|---|---|---|---|---|---|
| `display-xl` | 48px / 3rem | 1.1 | 800 | Plus Jakarta Sans | Hero headings (landing/marketing) |
| `display-lg` | 40px / 2.5rem | 1.15 | 800 | Plus Jakarta Sans | Page titles (Settings, Dashboard) |
| `display-md` | 32px / 2rem | 1.2 | 700 | Plus Jakarta Sans | Section headings |
| `heading-lg` | 24px / 1.5rem | 1.25 | 700 | Plus Jakarta Sans | Card group titles, section headers |
| `heading-md` | 20px / 1.25rem | 1.3 | 700 | Plus Jakarta Sans | Card titles, modal titles |
| `heading-sm` | 18px / 1.125rem | 1.35 | 700 | Plus Jakarta Sans | Subsection headings |
| `body-lg` | 16px / 1rem | 1.6 | 400–600 | Plus Jakarta Sans | Primary body text |
| `body-md` | 14px / 0.875rem | 1.55 | 400–600 | Plus Jakarta Sans | Secondary body, descriptions |
| `body-sm` | 13px / 0.8125rem | 1.5 | 400–700 | Plus Jakarta Sans | Buttons, nav items, form labels |
| `caption` | 12px / 0.75rem | 1.5 | 400–500 | Plus Jakarta Sans | Timestamps, helper text, badges |
| `overline` | 11px / 0.6875rem | 1.4 | 700 | Plus Jakarta Sans | Badge text, status labels |

### 3.3 Special Typography Treatments

#### Highlighted Title Underline
Page titles (`display-lg`) receive a yellow highlight underline effect:
- A `::after` pseudo-element with `yellow-200` background
- Height: 12px
- Positioned behind the bottom 30% of the text
- `border-radius: 4px`
- `transform: rotate(-0.5deg)` for a hand-drawn feel
- In dark mode, use `yellow-100` at 20% opacity

#### Gradient Text (Sparingly)
Used only for the page title on the landing/marketing page:
- `background: linear-gradient(135deg, text-primary, violet-500)`
- Apply with `background-clip: text` and `text-fill-color: transparent`
- Do NOT use gradient text inside the application UI — only marketing pages

### 3.4 Font Weight Semantic Mapping

| Weight Token | Value | Usage |
|---|---|---|
| `font-regular` | 400 | Body text, descriptions |
| `font-medium` | 500 | Navigation items, captions |
| `font-semibold` | 600 | Emphasized body, form labels |
| `font-bold` | 700 | Headings, button labels, card titles |
| `font-extrabold` | 800 | Display headings, logo, hero text |

---

## 4. Spacing & Layout

### 4.1 Spacing Scale (8px base unit)

| Token | Value | Common Usage |
|---|---|---|
| `space-0` | 0px | Reset |
| `space-1` | 4px | Tight inline gaps (icon–badge) |
| `space-2` | 8px | Inline element gaps, tight padding |
| `space-3` | 12px | Small component padding, list item gaps |
| `space-4` | 16px | Default component padding, standard gap |
| `space-5` | 20px | Card grid gaps, section sub-spacing |
| `space-6` | 24px | Card internal padding, component spacing |
| `space-7` | 32px | Page horizontal padding, nav padding |
| `space-8` | 40px | Section vertical spacing |
| `space-9` | 48px | Page top padding, major section breaks |
| `space-10` | 56px | Large section breaks |
| `space-11` | 64px | Hero spacing, page-level vertical rhythm |
| `space-12` | 80px | Maximum section spacing |

### 4.2 Layout Grid

#### Desktop (≥1200px)
- **Content max-width:** 1200px
- **Page padding:** `space-7` (32px) horizontal
- **Card grid:** 3 columns, `space-5` (20px) gap
- **Sidebar (if used):** 280px fixed width

#### Tablet (768px–1199px)
- **Content max-width:** 100%
- **Page padding:** `space-6` (24px) horizontal
- **Card grid:** 2 columns, `space-4` (16px) gap

#### Mobile (< 768px)
- **Content max-width:** 100%
- **Page padding:** `space-4` (16px) horizontal
- **Card grid:** 1 column, `space-4` (16px) gap
- **Nav:** Collapsed to hamburger menu

### 4.3 Content Hierarchy Spacing

| Between | Spacing Token |
|---|---|
| Page title → subtitle | `space-2` (8px) |
| Subtitle → first section | `space-8` (40px) |
| Section title → description | `space-2` (8px) |
| Description → content | `space-7` (32px) |
| Card grid rows | `space-5` (20px) |
| Card header → body | `space-4` (16px) |
| Card body → actions | `space-4` (16px) via padding-top on actions border |
| Tab bar → section content | `space-8` (40px) |
| Nav bar height | 70px (14px padding top/bottom + 42px logo) |
| Bottom bar height | 56px |

### 4.4 Z-Index Scale

| Token | Value | Usage |
|---|---|---|
| `z-background` | -1 | Background blobs, grain overlay |
| `z-base` | 0 | Default content |
| `z-card` | 1 | Elevated cards on hover |
| `z-sticky` | 10 | Sticky headers, bottom bar |
| `z-dropdown` | 20 | Dropdown menus, popovers |
| `z-modal` | 30 | Modal dialogs |
| `z-toast` | 40 | Toast notifications |
| `z-tooltip` | 50 | Tooltips |
| `z-max` | 100 | Style labels, debug overlays |

---

## 5. Elevation & Depth

### 5.1 Shadow Scale

| Token | Light Mode | Dark Mode | Usage |
|---|---|---|---|
| `shadow-none` | `none` | `none` | Default/resting state |
| `shadow-sm` | `0 2px 8px rgba(42,36,56,0.04)` | `0 2px 8px rgba(0,0,0,0.2)` | Subtle lift (badges) |
| `shadow-md` | `0 4px 16px rgba(42,36,56,0.06)` | `0 4px 16px rgba(0,0,0,0.25)` | Cards resting, dropdowns |
| `shadow-lg` | `0 12px 32px rgba(42,36,56,0.08)` | `0 12px 32px rgba(0,0,0,0.3)` | Cards on hover, modals |
| `shadow-xl` | `0 20px 48px rgba(42,36,56,0.12)` | `0 20px 48px rgba(0,0,0,0.4)` | Modals, toasts |
| `shadow-color-violet` | `0 4px 16px rgba(99,102,241,0.25)` | `0 4px 16px rgba(129,140,248,0.2)` | Active nav, violet buttons |
| `shadow-color-teal` | `0 4px 16px rgba(46,196,182,0.3)` | `0 4px 16px rgba(64,214,200,0.2)` | Active tab |
| `shadow-color-blue` | `0 4px 16px rgba(59,130,246,0.2)` | `0 4px 16px rgba(96,165,250,0.15)` | CTA gradient buttons |
| `shadow-glow` | `0 0 8px currentColor` | `0 0 12px currentColor` | Deprecated - use specific shadow values |

### 5.2 Background Blobs Specification

Four fixed-position blurred circles create the atmospheric background:

| Blob | Position | Size | Color Token | Blur |
|---|---|---|---|---|
| blob-1 | `top: -60px; left: 10%` | 400×400px | `blob-blue` | 80px |
| blob-2 | `top: 30%; right: -80px` | 350×350px | `blob-violet` | 80px |
| blob-3 | `bottom: -40px; left: 30%` | 450×450px | `blob-teal` | 80px |
| blob-4 | `top: 50%; left: -100px` | 300×300px | `blob-slate` | 80px |

> **Dark mode:** Reduce all blob opacities by ~40% (values in token table above). **v2.0 Note:** Blob colors updated to match the cooler color palette.

### 5.3 Grain Texture

Apply a subtle noise texture over the entire viewport:
- SVG-based fractalNoise filter: `baseFrequency: 0.8`, `numOctaves: 4`
- Light mode opacity: `0.02` (refined in v2.0)
- Dark mode opacity: `0.04` (refined in v2.0)
- `position: fixed`, `pointer-events: none`, covers full viewport
- Z-index: `z-background`
- **Design Note:** Grain opacity reduced in v2.0 for a cleaner, more refined appearance

---

## 6. Border & Radius

### 6.1 Border Radius Scale (Moderated in v2.0)

| Token | Value | Usage |
|---|---|---|
| `radius-none` | 0px | No rounding |
| `radius-sm` | 4px | Grain overlay, minor elements |
| `radius-md` | 8px | Buttons, inputs, nav items, tabs |
| `radius-lg` | 12px | Card icons, icon containers |
| `radius-xl` | 16px | Cards, modals, panels |
| `radius-pill` | 50px | Pill tabs, badges, pill buttons |
| `radius-circle` | 50% | Avatars, status dots |

**Design Note:** Border radii have been moderated in v2.0 for a more professional, balanced aesthetic. Previously more rounded values (md: 14px, lg: 16px, xl: 24px) have been reduced while maintaining the design's friendly personality.

### 6.2 Border Widths

| Token | Value | Usage |
|---|---|---|
| `border-thin` | 1px | Subtle dividers |
| `border-default` | 2px | Card borders, input borders, tab borders |
| `border-thick` | 3px | Nav rainbow border, bottom bar rainbow |
| `border-accent` | 4px | Card left accent border |
| `border-dashed` | 2px dashed | Card action dividers |

### 6.3 Signature Rainbow Border

The multi-color gradient border is a core brand element. Apply using `border-image`:

```
border-width: 3px;
border-style: solid;
border-image: linear-gradient(90deg, coral-500, yellow-500, teal-500, violet-500) 1;
```

Used on: top nav bottom border, bottom bar top border, section dividers, loading progress bars.

---

## 7. Animations & Motion

### 7.1 Motion Principles

- **Playful but not distracting** — Motion should feel like a wink, not a circus act
- **Physics-based** — Use spring/bounce easing for personality, not linear easing
- **Reduced motion** — All animations must respect `prefers-reduced-motion: reduce`; use `opacity` transitions as fallback
- **Direction** — Elements generally animate from bottom-up (enter) and top-down (exit)

### 7.2 Easing Curves (Refined in v2.0)

| Token | Value | Usage |
|---|---|---|
| `ease-default` | `cubic-bezier(0.4, 0, 0.2, 1)` | Standard transitions |
| `ease-bounce` | `cubic-bezier(0.34, 1.2, 0.64, 1)` | Card hover, button press, playful elements |
| `ease-spring` | `cubic-bezier(0.175, 0.885, 0.32, 1.1)` | Modals, popovers entering |
| `ease-smooth` | `cubic-bezier(0.25, 0.1, 0.25, 1)` | Color transitions, fades |
| `ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | Exit animations |

**Design Note:** The bounce and spring easing curves have been refined in v2.0 to reduce overshoot (from 1.56 to 1.2 for bounce, 1.275 to 1.1 for spring). This creates more subtle, professional animations while preserving the playful character of the design.

### 7.3 Duration Scale

| Token | Value | Usage |
|---|---|---|
| `duration-instant` | 100ms | Color changes, opacity |
| `duration-fast` | 200ms | Button state changes, hover effects |
| `duration-default` | 300ms | Card hover, dropdown open |
| `duration-moderate` | 400ms | Modal transitions, page elements |
| `duration-slow` | 600ms | Staggered reveals, complex transitions |
| `duration-dramatic` | 800ms | Hero animations, page load sequences |

### 7.4 Signature Animations

#### Card Hover
```
transform: translateY(-4px) rotate(-0.5deg);
box-shadow: shadow-lg;
border-color: violet-300;
transition: all duration-default ease-bounce;
```

#### Button Hover (Primary)
```
transform: translateY(-2px) rotate(-1deg);
box-shadow: shadow-color-violet (or appropriate color shadow);
transition: all duration-fast ease-bounce;
```

#### Page Load — Staggered Card Reveal
Cards animate in sequentially with a 80ms delay between each:
```
@keyframes cardReveal {
  from {
    opacity: 0;
    transform: translateY(20px) rotate(-1deg);
  }
  to {
    opacity: 1;
    transform: translateY(0) rotate(0);
  }
}
animation: cardReveal duration-moderate ease-spring;
animation-delay: calc(var(--card-index) * 80ms);
animation-fill-mode: backwards;
```

#### Tab Switch
Active tab pill slides into position with:
```
transition: all duration-default ease-bounce;
/* No rotation on active tab state */
```

#### Status Badge Pulse (Error State)
```
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
animation: pulse 2s ease-in-out infinite;
```

#### Modal Enter
```
@keyframes modalEnter {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
animation: modalEnter duration-moderate ease-spring;
```

#### Toast Notification Enter
```
@keyframes toastEnter {
  from {
    opacity: 0;
    transform: translateX(100%) rotate(2deg);
  }
  to {
    opacity: 1;
    transform: translateX(0) rotate(0);
  }
}
animation: toastEnter duration-default ease-bounce;
```

#### Background Blob Drift (Optional, CPU-permitting)
```
@keyframes blobDrift {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(15px, -10px); }
  66% { transform: translate(-10px, 15px); }
}
animation: blobDrift 20s ease-in-out infinite;
```

### 7.5 Reduced Motion Fallback

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

All hover transforms (rotation, translateY) should be disabled. Only opacity changes are preserved.

---

## 8. Component Guidelines

### 8.1 Top Navigation Bar

**Structure:** Full-width bar, fixed at top, content centered at max-width.

| Property | Value |
|---|---|
| Height | 70px |
| Background | `bg-elevated` |
| Bottom border | `border-thick` using `gradient-rainbow` |
| Padding | `14px space-7` |

**Logo Mark:**
- Size: 42×42px
- Shape: `radius-lg` (16px)
- Background: `gradient-cta`
- Font: `font-display`, weight 800, 20px, `text-inverse`
- `transform: rotate(-3deg)`
- Shadow: `shadow-color-violet`

**Nav Items:**
- Font: `body-sm` (13px), `font-bold` (700)
- Color: `text-tertiary` → hover: `violet-500` on `violet-100` bg
- Active: `bg: violet-500`, `color: text-inverse`, `shadow-color-violet`
- Padding: `8px 16px`
- Radius: `radius-md`
- Icon: 18×18px, stroke-width 2, inline before text with `space-2` gap

**Status Dots:**
- Size: 10×10px (or 2.5px for compact indicators)
- Border radius: `radius-circle`
- Shadow: `0 0 4px rgba(0, 0, 0, 0.15)` (refined in v2.0 for subtlety)
- Colors cycle through session colors
- **Design Note:** Shadow reduced from `var(--shadow-glow)` (0 0 8px) to 4px blur for a more refined appearance

**Theme Toggle:**
- Size: 36×36px
- Radius: `radius-md`
- Border: `border-default` using `border-default` color
- Background: `bg-elevated`
- `transform: rotate(8deg)`
- **Icon Logic (v2.0):** Shows moon icon (slate-500) in light mode to indicate switching to dark; shows sun icon (amber-400) in dark mode to indicate switching to light
- **Design Note:** Icons represent the destination mode, not the current mode, following modern UX patterns

### 8.2 Tab Bar

**Container:**
- Layout: Horizontal flex, `space-3` (8px) gap
- No background (sits on page bg)
- Margin-bottom: `space-8`

**Individual Tabs:**
- Font: `body-sm`, `font-bold`
- Padding: `10px 22px`
- Radius: `radius-pill`
- Border: `border-default` solid `border-default` color
- Background: `bg-elevated`
- Color: `text-tertiary`

**Tab States:**
| State | Background | Color | Border | Transform | Shadow |
|---|---|---|---|---|---|
| Default | `bg-elevated` | `text-tertiary` | `border-default` | none | none |
| Hover | `bg-elevated` | `teal-500` | `teal-300` | `translateY(-2px)` | none |
| Active | `teal-500` | `text-inverse` | `teal-500` | none | `shadow-color-teal` |
| Focus | Same as hover | — | `violet-500` outline 2px offset 2px | — | — |

### 8.3 Integration Cards

**Container:**
- Background: `bg-elevated`
- Border: `border-default` solid `border-default` color
- Border-left: `border-accent` solid (color cycles per `accent-slot-N`)
- Radius: `radius-xl`
- Padding: `space-6`

**Card Hover:**
- Transform: `translateY(-4px) rotate(-0.5deg)`
- Shadow: `shadow-lg`
- Border-color: `violet-300`
- Transition: `all duration-default ease-bounce`

**Card Icon:**
- Size: 48×48px
- Radius: `radius-lg`
- Background: Color-matched to the card's accent slot (use the `-100` shade)
- Contains emoji or SVG icon at 22px

**Card Title:**
- Font: `heading-md` (Fraunces, 700, 18px)

**Status Badge:**
- Font: `overline` (11px, 700)
- Padding: `3px 14px`
- Radius: `radius-pill`
- Uses semantic color tokens (`success-bg`/`success-text`, `error-bg`/`error-text`, `disconnected-bg`/`disconnected`)

**Timestamp:**
- Font: `caption` (12px, 400)
- Color: `text-tertiary`

**Action Divider:**
- `border-dashed` in `border-default` color
- Margin-top: `space-4`

**Action Buttons:**
See Button component spec below.

### 8.4 Buttons

#### Primary Button
| Property | Value |
|---|---|
| Background | `violet-500` |
| Color | `text-inverse` |
| Border | `border-default` solid `violet-500` |
| Radius | `radius-md` |
| Padding | `10px space-4` |
| Font | `body-sm`, `font-bold` |
| Shadow | `shadow-color-violet` |

| State | Changes |
|---|---|
| Hover | `translateY(-2px) rotate(-1deg)`, increase shadow spread |
| Active/Pressed | `translateY(0)`, shadow reduces |
| Focus | 2px `violet-300` outline, 2px offset |
| Disabled | `bg: surface-muted`, `color: text-disabled`, no shadow, no transform |

#### Primary CTA Button (gradient)
| Property | Value |
|---|---|
| Background | `gradient-cta` |
| Color | `text-inverse` |
| Border | none |
| Shadow | `shadow-color-coral` |

Used for high-emphasis actions: "Get Started", "Connect", main page CTAs.

#### Secondary Button
| Property | Value |
|---|---|
| Background | transparent |
| Color | `text-tertiary` |
| Border | `border-default` solid `border-default` color |
| Radius | `radius-md` |

| State | Changes |
|---|---|
| Hover | Border-color: `coral-300`, color: `coral-500`, `translateY(-1px)` |
| Focus | 2px `violet-300` outline, 2px offset |
| Disabled | `color: text-disabled`, `border: border-subtle` |

#### Ghost Button
- Same as Secondary but no border in default state
- Border appears on hover
- Used inside dropdowns, menus, less emphasized actions

#### Destructive Button
- Same structure as Primary, but `error` color instead of `violet-500`
- Shadow: `shadow-color-coral`
- Used for "Delete", "Remove", "Disconnect" confirmations

### 8.5 Badges / Status Indicators

| Variant | Background | Text Color | Border |
|---|---|---|---|
| Connected/Success | `success-bg` | `success-text` | none |
| Error | `error-bg` | `error-text` | none |
| Warning | `warning-bg` | `warning-text` | none |
| Disconnected | `disconnected-bg` | `disconnected` | none |
| Info | `info-bg` | `info-text` | none |
| Neutral | `surface-muted` | `text-secondary` | none |

All badges: `radius-pill`, `caption` font size, `font-bold`, padding `3px 14px`.

### 8.6 Bottom Bar / AI Assistant Bar

| Property | Value |
|---|---|
| Position | Fixed bottom |
| Height | 56px |
| Background | `bg-elevated` |
| Top border | `border-thick` using `gradient-rainbow` |
| Padding | `12px space-7` |
| Z-index | `z-sticky` |

**Assistant Icon:**
- Size: 32×32px
- Radius: `radius-md` (12px)
- Background: `gradient-subtle`
- `transform: rotate(-5deg)`

**Help Button:**
- Size: 34×34px
- Radius: `radius-circle`
- Border: `border-default` solid `yellow-500`
- Background: `yellow-100`
- Font: `body-sm`, `font-extrabold`
- `transform: rotate(6deg)`

### 8.7 Modal / Dialog

| Property | Value |
|---|---|
| Max-width | 520px (small), 720px (medium), 960px (large) |
| Radius | `radius-xl` |
| Background | `bg-elevated` |
| Border | `border-default` solid `border-default` |
| Shadow | `shadow-xl` |
| Padding | `space-7` (32px) |
| Overlay | `bg-overlay` |
| Animation | `modalEnter` |

### 8.8 Toast Notifications

| Property | Value |
|---|---|
| Position | Fixed, top-right, 20px from edges |
| Max-width | 400px |
| Radius | `radius-xl` |
| Background | `bg-elevated` |
| Border-left | `border-accent` solid (semantic color) |
| Shadow | `shadow-lg` |
| Animation | `toastEnter` |
| Auto-dismiss | 5 seconds, with progress bar using `gradient-rainbow` |

---

## 9. Chat Interface Components

### 9.1 Chat Container Layout

| Property | Value |
|---|---|
| Width | Full available width (within app content area) |
| Max message width | 720px, centered |
| Background | `bg-primary` with blob effects |
| Padding (messages area) | `space-6` horizontal, `space-4` vertical between messages |

### 9.2 User Message Bubble

| Property | Value |
|---|---|
| Background | `violet-500` |
| Color | `text-inverse` |
| Radius | `radius-xl` with bottom-right `radius-sm` |
| Padding | `space-4 space-5` (16px 20px) |
| Max-width | 75% of container |
| Alignment | Right-aligned |
| Font | `body-md`, `font-regular` |
| Shadow | `shadow-sm` |

### 9.3 AI Message Bubble

| Property | Value |
|---|---|
| Background | `bg-elevated` |
| Color | `text-primary` |
| Border | `border-thin` solid `border-default` |
| Border-left | `border-accent` solid `teal-500` |
| Radius | `radius-xl` with bottom-left `radius-sm` |
| Padding | `space-4 space-5` |
| Max-width | 85% of container |
| Alignment | Left-aligned |
| Font | `body-md`, `font-regular` |

**AI Avatar:**
- Size: 32×32px
- Radius: `radius-md`
- Background: `gradient-subtle`
- Position: Above message, left-aligned
- Displays "K" in `font-display`, `font-extrabold`, 14px
- `transform: rotate(-3deg)`

### 9.4 Typing Indicator

Three dots inside an AI-style bubble:
- Dot size: 8px
- Dot color: `teal-500`, `violet-500`, `coral-500` (one each)
- Animation: Sequential bounce with 150ms delay between dots
```
@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}
```
- Duration: 1.4s per cycle, infinite

### 9.5 Chat Input Bar

| Property | Value |
|---|---|
| Position | Sticky bottom of chat container |
| Background | `bg-elevated` |
| Border | `border-default` solid `border-default` |
| Border-top | `border-thick` using `gradient-rainbow` |
| Radius | `radius-xl` |
| Padding | `space-3 space-4` |
| Shadow | `shadow-md` |

**Input Field:**
- No visible border (border is on the container)
- Font: `body-lg`, `font-regular`
- Placeholder color: `text-tertiary`
- Grows vertically with content up to 200px

**Send Button:**
- Size: 40×40px
- Radius: `radius-md`
- Background: `gradient-cta`
- Icon: Arrow-up, 20px, `text-inverse`
- Shadow: `shadow-color-coral`
- Disabled: `surface-muted` background, `text-disabled` icon

### 9.6 Message Actions (hover overlay)

| Property | Value |
|---|---|
| Visibility | Appears on message hover |
| Position | Top-right of message bubble |
| Background | `bg-elevated` |
| Border | `border-thin` solid `border-default` |
| Radius | `radius-md` |
| Shadow | `shadow-sm` |
| Icons | Copy, Regenerate, Thumbs Up/Down — each 28×28px ghost buttons |

### 9.7 Session Tabs (concurrent sessions)

| Property | Value |
|---|---|
| Layout | Horizontal scrollable row above chat area |
| Tab style | Same as main Tab Bar component |
| Active indicator | `teal-500` bottom accent bar |
| Max visible | 5 tabs, then horizontal scroll with fade edges |
| "New Session" | Ghost button with `+` icon, dashed border |

---

## 10. Form Elements

### 10.1 Text Input

| Property | Default | Focus | Error | Disabled |
|---|---|---|---|---|
| Background | `bg-elevated` | `bg-elevated` | `bg-elevated` | `surface-muted` |
| Border | `border-default` `border-default` | `border-default` `violet-500` | `border-default` `error` | `border-thin` `border-subtle` |
| Radius | `radius-md` | — | — | — |
| Padding | `12px space-4` | — | — | — |
| Font | `body-md`, `font-regular` | — | — | `text-disabled` |
| Color | `text-primary` | — | — | `text-disabled` |
| Shadow | none | `0 0 0 3px violet-100` | `0 0 0 3px coral-100` | none |
| Transition | `all duration-fast ease-default` | — | — | — |

**Label:** `body-sm`, `font-semibold`, `text-primary`, margin-bottom `space-2`.
**Helper Text:** `caption`, `text-tertiary`, margin-top `space-1`.
**Error Text:** `caption`, `error-text`, margin-top `space-1`.

### 10.2 Textarea

Same as Text Input, with:
- Min-height: 80px
- Resize: vertical
- Max-height: 240px

### 10.3 Select / Dropdown

**Trigger:** Same as Text Input, plus chevron-down icon (16px) right-aligned in `text-tertiary`.

**Dropdown Panel:**
| Property | Value |
|---|---|
| Background | `bg-elevated` |
| Border | `border-default` solid `border-default` |
| Radius | `radius-xl` |
| Shadow | `shadow-lg` |
| Padding | `space-2` |
| Animation | `modalEnter` (scale from 0.95 + fade) |
| Max-height | 280px, scrollable |

**Dropdown Option:**
- Padding: `10px space-4`
- Radius: `radius-md`
- Hover: `violet-100` background, `violet-500` text
- Selected: `teal-100` background, `teal-500` text, checkmark icon

### 10.4 Checkbox

| Property | Unchecked | Checked | Disabled |
|---|---|---|---|
| Size | 20×20px | 20×20px | 20×20px |
| Border | `border-default` `border-strong` | none | `border-thin` `border-subtle` |
| Radius | `radius-sm` (4px) | `radius-sm` | `radius-sm` |
| Background | `bg-elevated` | `violet-500` | `surface-muted` |
| Check icon | — | White, 14px, animated scale-in | Faded |
| Shadow (focus) | — | `0 0 0 3px violet-100` | — |

Check animation: `scale(0) → scale(1.2) → scale(1)` over `duration-fast` with `ease-bounce`.

### 10.5 Toggle / Switch

| Property | Off | On | Disabled |
|---|---|---|---|
| Track size | 44×24px | 44×24px | 44×24px |
| Track color | `border-default` | `teal-500` | `surface-muted` |
| Track radius | `radius-pill` | `radius-pill` | `radius-pill` |
| Thumb size | 18×18px | 18×18px | 18×18px |
| Thumb color | `bg-elevated` | `bg-elevated` | `text-disabled` |
| Thumb position | Left (3px inset) | Right (3px inset) | — |
| Thumb shadow | `shadow-sm` | `shadow-sm` | none |
| Transition | `all duration-fast ease-bounce` | — | — |

Focus: `0 0 0 3px violet-100` ring on track.

### 10.6 Radio Button

| Property | Unselected | Selected |
|---|---|---|
| Size | 20×20px | 20×20px |
| Border | `border-default` `border-strong` | `border-default` `violet-500` |
| Radius | `radius-circle` | `radius-circle` |
| Inner dot | — | 8px, `violet-500`, centered, animated scale-in |
| Focus | `0 0 0 3px violet-100` | `0 0 0 3px violet-100` |

### 10.7 Slider / Range

| Property | Value |
|---|---|
| Track height | 6px |
| Track color (unfilled) | `border-default` |
| Track color (filled) | `gradient-rainbow` |
| Track radius | `radius-pill` |
| Thumb size | 22×22px |
| Thumb color | `bg-elevated` |
| Thumb border | `border-default` `violet-500` |
| Thumb radius | `radius-circle` |
| Thumb shadow | `shadow-md` |
| Thumb hover | Scale to 26px, `shadow-color-violet` |

### 10.8 Search Input

Same as Text Input, with:
- Left icon: Search (magnifying glass), 18px, `text-tertiary`
- Left padding increased to 44px to accommodate icon
- Clear button (X): appears when value present, right-aligned, ghost button style

---

## 11. Data Visualization

### 11.1 Chart Color Palette

Charts use the core brand colors in this specific order for data series:

| Series | Color (Light) | Color (Dark) |
|---|---|---|
| 1 | `#7B68EE` (violet) | `#9588FF` |
| 2 | `#2EC4B6` (teal) | `#40D6C8` |
| 3 | `#FF6B6B` (coral) | `#FF8A8A` |
| 4 | `#FFD93D` (yellow) | `#FFE066` |
| 5 | `#B8ADFF` (violet-300) | `#7468CC` |
| 6 | `#A8E6E0` (teal-300) | `#2A6B62` |
| 7 | `#FFB3B3` (coral-300) | `#8B4444` |
| 8 | `#FFF0A0` (yellow-300) | `#6B6030` |

If more than 8 series, add 30% opacity variants of series 1–4.

### 11.2 Chart Grid & Axis

| Element | Light Mode | Dark Mode |
|---|---|---|
| Grid lines | `border-subtle` (1px) | `border-subtle` |
| Axis lines | `border-default` (1.5px) | `border-default` |
| Axis labels | `caption` size, `text-tertiary` | `text-tertiary` |
| Tick marks | `border-default`, 4px long | `border-default` |

### 11.3 Chart Container

| Property | Value |
|---|---|
| Background | `bg-elevated` |
| Border | `border-default` solid `border-default` |
| Radius | `radius-xl` |
| Padding | `space-6` |
| Title font | `heading-sm` (Fraunces, 18px, 700) |
| Subtitle font | `caption`, `text-tertiary` |

### 11.4 Chart Tooltip

| Property | Value |
|---|---|
| Background | `bg-elevated` (light) / `#2A2438` (dark) |
| Border | `border-thin` solid `border-default` |
| Radius | `radius-md` |
| Shadow | `shadow-lg` |
| Padding | `space-3 space-4` |
| Font | `caption` for labels, `body-sm` `font-bold` for values |
| Color indicator | 8px circle matching series color |
| Animation | Fade in `duration-instant` |
| Pointer offset | 8px from cursor |

### 11.5 Chart Specific Guidelines

**Bar Charts:**
- Bar radius: top corners `radius-sm` (4px)
- Bar gap: 30% of bar width
- Hover: Bar lightens 15%, tooltip appears
- Playful touch: Bars animate in from bottom on load with stagger (`80ms` per bar), `ease-bounce`

**Line Charts:**
- Stroke width: 2.5px
- Point dots: 5px radius, filled with series color, white 2px stroke
- Point dots on hover: Scale to 7px
- Area fill: Series color at 10% opacity
- Animate: Line draws from left to right on load (`duration-dramatic`)

**Donut/Pie Charts:**
- Stroke width (donut): 40px
- Gap between segments: 2px (white/bg gap)
- Center text: `heading-lg` for value, `caption` for label
- Hover: Segment expands outward 4px
- Playful touch: Segments animate in clockwise on load

**Sparklines (inline):**
- Height: 32px
- Stroke: 2px, single series color
- No axes, no labels
- Optional: Faint area fill at 8% opacity

### 11.6 KPI Cards (for dashboards)

| Property | Value |
|---|---|
| Background | `bg-elevated` |
| Border-left | `border-accent` (cycles color per card) |
| Radius | `radius-xl` |
| Padding | `space-6` |
| KPI Value | `display-md` (Fraunces, 32px, 700) |
| KPI Label | `body-sm`, `text-secondary` |
| Trend indicator | `caption`, `success-text` (up) or `error-text` (down), with ↑/↓ arrow |
| Sparkline | Inline, right-aligned, 80px wide × 32px tall |

---

## 12. Iconography

### 12.1 Icon Style

| Property | Value |
|---|---|
| Library | Lucide Icons (primary), custom emoji for integration logos |
| Stroke width | 2px |
| Style | Rounded line icons (consistent with Lucide defaults) |
| Default size | 18px (nav), 20px (buttons/forms), 24px (section headers) |
| Color | Inherits `currentColor` from parent |

### 12.2 Integration Icons

Integration cards use emoji as a deliberate design choice (playful, cross-platform, instantly recognizable):

| Integration | Emoji | Fallback |
|---|---|---|
| Google Ads | 🔍 | Lucide `search` |
| HubSpot | 🧡 | Lucide `heart` |
| Meta Ads | 📘 | Lucide `book-open` |
| Salesforce | ☁️ | Lucide `cloud` |
| LinkedIn Ads | 💼 | Lucide `briefcase` |
| Mailchimp | 📧 | Lucide `mail` |
| AI Assistant | 💬 | Lucide `message-circle` |

### 12.3 Icon Container Backgrounds

Icon containers in cards match the card's accent color at the `100` (lightest) shade:
- Violet accent cards: `violet-100` icon bg
- Blue accent cards: `blue-100` icon bg
- Teal accent cards: `teal-100` icon bg
- Amber accent cards: `amber-100` icon bg
- Slate accent cards: `slate-100` icon bg

---

## 13. CSS Custom Properties

### 13.1 Full Token Export — Light Mode

```css
:root {
  /* --- Core Brand --- */
  --color-coral-100: #FFF0F0;
  --color-coral-200: #FFD4D4;
  --color-coral-300: #FFB3B3;
  --color-coral-400: #FF8A8A;
  --color-coral-500: #FF6B6B;
  --color-teal-100: #E8F8F6;
  --color-teal-200: #C4EDE8;
  --color-teal-300: #A8E6E0;
  --color-teal-400: #6AD8CC;
  --color-teal-500: #2EC4B6;
  --color-violet-100: #EEEAFF;
  --color-violet-200: #D4CCFF;
  --color-violet-300: #B8ADFF;
  --color-violet-400: #9C8EFF;
  --color-violet-500: #7B68EE;
  --color-yellow-100: #FFFBE6;
  --color-yellow-200: #FFF5C4;
  --color-yellow-300: #FFF0A0;
  --color-yellow-400: #FFE566;
  --color-yellow-500: #FFD93D;

  /* --- Surfaces --- */
  --color-bg-primary: #FFFBF5;
  --color-bg-secondary: #FFF5EC;
  --color-bg-elevated: #FFFFFF;
  --color-bg-overlay: rgba(42, 36, 56, 0.5);
  --color-surface-muted: #F8F4F0;

  /* --- Text --- */
  --color-text-primary: #2A2438;
  --color-text-secondary: #5A5068;
  --color-text-tertiary: #9088A0;
  --color-text-disabled: #C4BCD0;
  --color-text-inverse: #FFFFFF;

  /* --- Borders --- */
  --color-border-default: #E8E0F0;
  --color-border-subtle: #F0ECF4;
  --color-border-strong: #C4BCD0;

  /* --- Semantic --- */
  --color-success: #2EC4B6;
  --color-success-bg: #E8F8F6;
  --color-success-text: #1A756B;
  --color-error: #E05252;
  --color-error-bg: #FFF0F0;
  --color-error-text: #9E2020;
  --color-warning: #D4960A;
  --color-warning-bg: #FFFBE6;
  --color-warning-text: #8B6400;
  --color-info: #5A6FCC;
  --color-info-bg: #EEEAFF;
  --color-info-text: #3A4A8C;
  --color-disconnected: #9088A0;
  --color-disconnected-bg: #F0ECF4;

  /* --- Gradients --- */
  --gradient-rainbow: linear-gradient(90deg, #FF6B6B, #FFD93D, #2EC4B6, #7B68EE);
  --gradient-cta: linear-gradient(135deg, #FF6B6B, #7B68EE);
  --gradient-subtle: linear-gradient(135deg, #A8E6E0, #B8ADFF);

  /* --- Blobs --- */
  --color-blob-coral: rgba(255, 107, 107, 0.15);
  --color-blob-violet: rgba(123, 104, 238, 0.15);
  --color-blob-teal: rgba(46, 196, 182, 0.10);
  --color-blob-yellow: rgba(255, 217, 61, 0.12);
  --grain-opacity: 0.03;

  /* --- Card Accent Slots --- */
  --color-accent-slot-1: #FF6B6B;
  --color-accent-slot-2: #FFD93D;
  --color-accent-slot-3: #7B68EE;
  --color-accent-slot-4: #FF6B6B;
  --color-accent-slot-5: #2EC4B6;
  --color-accent-slot-6: #7B68EE;

  /* --- Typography --- */
  --font-display: 'Fraunces', Georgia, serif;
  --font-body: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-regular: 400;
  --font-medium: 500;
  --font-semibold: 600;
  --font-bold: 700;
  --font-extrabold: 800;

  /* --- Type Scale --- */
  --text-display-xl: 48px;
  --text-display-lg: 40px;
  --text-display-md: 32px;
  --text-heading-lg: 24px;
  --text-heading-md: 20px;
  --text-heading-sm: 18px;
  --text-body-lg: 16px;
  --text-body-md: 14px;
  --text-body-sm: 13px;
  --text-caption: 12px;
  --text-overline: 11px;
  --lh-display-xl: 1.1;
  --lh-display-lg: 1.15;
  --lh-display-md: 1.2;
  --lh-heading-lg: 1.25;
  --lh-heading-md: 1.3;
  --lh-heading-sm: 1.35;
  --lh-body: 1.6;
  --lh-body-md: 1.55;
  --lh-body-sm: 1.5;
  --lh-caption: 1.5;

  /* --- Spacing --- */
  --space-0: 0px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --space-9: 48px;
  --space-10: 56px;
  --space-11: 64px;
  --space-12: 80px;

  /* --- Radii --- */
  --radius-none: 0px;
  --radius-sm: 4px;
  --radius-md: 14px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --radius-pill: 50px;
  --radius-circle: 50%;

  /* --- Borders --- */
  --border-thin: 1px;
  --border-default: 2px;
  --border-thick: 3px;
  --border-accent: 4px;

  /* --- Shadows --- */
  --shadow-none: none;
  --shadow-sm: 0 2px 8px rgba(42, 36, 56, 0.04);
  --shadow-md: 0 4px 16px rgba(42, 36, 56, 0.06);
  --shadow-lg: 0 12px 32px rgba(42, 36, 56, 0.08);
  --shadow-xl: 0 20px 48px rgba(42, 36, 56, 0.12);
  --shadow-color-violet: 0 4px 16px rgba(123, 104, 238, 0.25);
  --shadow-color-teal: 0 4px 16px rgba(46, 196, 182, 0.3);
  --shadow-color-coral: 0 4px 16px rgba(255, 107, 107, 0.2);

  /* --- Motion --- */
  --ease-default: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
  --ease-smooth: cubic-bezier(0.25, 0.1, 0.25, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --duration-instant: 100ms;
  --duration-fast: 200ms;
  --duration-default: 300ms;
  --duration-moderate: 400ms;
  --duration-slow: 600ms;
  --duration-dramatic: 800ms;

  /* --- Z-Index --- */
  --z-background: -1;
  --z-base: 0;
  --z-card: 1;
  --z-sticky: 10;
  --z-dropdown: 20;
  --z-modal: 30;
  --z-toast: 40;
  --z-tooltip: 50;
  --z-max: 100;
}
```

### 13.2 Dark Mode Overrides

```css
[data-theme="dark"], .dark {
  /* --- Core Brand (boosted for dark bg) --- */
  --color-coral-100: #3D1F1F;
  --color-coral-200: #5C2E2E;
  --color-coral-300: #8B4444;
  --color-coral-400: #CC6060;
  --color-coral-500: #FF8A8A;
  --color-teal-100: #132D2A;
  --color-teal-200: #1E4A44;
  --color-teal-300: #2A6B62;
  --color-teal-400: #36A898;
  --color-teal-500: #40D6C8;
  --color-violet-100: #1E1A33;
  --color-violet-200: #2E2850;
  --color-violet-300: #4A4080;
  --color-violet-400: #7468CC;
  --color-violet-500: #9588FF;
  --color-yellow-100: #332E13;
  --color-yellow-200: #4D451E;
  --color-yellow-300: #6B6030;
  --color-yellow-400: #B3A040;
  --color-yellow-500: #FFE066;

  /* --- Surfaces --- */
  --color-bg-primary: #1A1625;
  --color-bg-secondary: #221D30;
  --color-bg-elevated: #2A2438;
  --color-bg-overlay: rgba(0, 0, 0, 0.6);
  --color-surface-muted: #2E2840;

  /* --- Text --- */
  --color-text-primary: #F5F0FA;
  --color-text-secondary: #B8ADCC;
  --color-text-tertiary: #7A708E;
  --color-text-disabled: #4A4260;
  --color-text-inverse: #1A1625;

  /* --- Borders --- */
  --color-border-default: #3A3250;
  --color-border-subtle: #2E2840;
  --color-border-strong: #5A5070;

  /* --- Semantic --- */
  --color-success: #40D6C8;
  --color-success-bg: #132D2A;
  --color-success-text: #40D6C8;
  --color-error: #FF7A7A;
  --color-error-bg: #3D1F1F;
  --color-error-text: #FF7A7A;
  --color-warning: #FFD93D;
  --color-warning-bg: #332E13;
  --color-warning-text: #FFD93D;
  --color-info: #8A9AFF;
  --color-info-bg: #1E1A33;
  --color-info-text: #8A9AFF;
  --color-disconnected: #7A708E;
  --color-disconnected-bg: #2E2840;

  /* --- Gradients --- */
  --gradient-rainbow: linear-gradient(90deg, #FF8A8A, #FFE066, #40D6C8, #9588FF);
  --gradient-cta: linear-gradient(135deg, #FF8A8A, #9588FF);
  --gradient-subtle: linear-gradient(135deg, #2A6B62, #4A4080);

  /* --- Blobs --- */
  --color-blob-coral: rgba(255, 107, 107, 0.08);
  --color-blob-violet: rgba(123, 104, 238, 0.08);
  --color-blob-teal: rgba(46, 196, 182, 0.06);
  --color-blob-yellow: rgba(255, 217, 61, 0.06);
  --grain-opacity: 0.05;

  /* --- Card Accent Slots (brighter for dark bg) --- */
  --color-accent-slot-1: #FF8A8A;
  --color-accent-slot-2: #FFE066;
  --color-accent-slot-3: #9588FF;
  --color-accent-slot-4: #FF8A8A;
  --color-accent-slot-5: #40D6C8;
  --color-accent-slot-6: #9588FF;

  /* --- Shadows --- */
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.2);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.25);
  --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.3);
  --shadow-xl: 0 20px 48px rgba(0, 0, 0, 0.4);
  --shadow-color-violet: 0 4px 16px rgba(149, 136, 255, 0.2);
  --shadow-color-teal: 0 4px 16px rgba(64, 214, 200, 0.2);
  --shadow-color-coral: 0 4px 16px rgba(255, 138, 138, 0.15);
}
```

---

## 14. Figma Implementation Notes

### 14.1 File Structure

Organize the Figma file with these pages:

```
📄 Cover
📄 Design Principles (text page with the 5 pillars)
📄 Color Tokens
📄 Typography
📄 Iconography
📄 Components
   ├── Buttons
   ├── Badges
   ├── Inputs
   ├── Tabs
   ├── Cards
   ├── Navigation
   ├── Chat Components
   ├── Charts
   ├── Modals & Overlays
   └── Toast Notifications
📄 Patterns
   ├── Settings Page
   ├── Chat Interface
   ├── Dashboard
   └── Empty States
📄 Dark Mode (duplicate of Components with dark theme applied)
```

### 14.2 Figma Variables Setup

Create these variable collections:

**Collection: `Primitives`**
- All color scales (coral-100 through coral-500, etc.)
- All spacing values
- All radius values
- All font sizes

**Collection: `Semantic` (references Primitives)**
- Mode: Light / Dark
- Map semantic names to primitive values
- Example: `bg-primary` → Light: `#FFFBF5` / Dark: `#1A1625`

**Collection: `Component`**
- Component-specific tokens that reference Semantic
- Example: `card-bg` → `bg-elevated`, `card-border` → `border-default`

### 14.3 Figma Styles

Create these shared styles:

**Color Styles:** Every token from the Color Palette section (grouped by category: Brand/, Neutral/, Semantic/, Gradient/).

**Text Styles:** Every entry from the Type Scale table. Name format: `Display/XL`, `Heading/LG`, `Body/MD`, etc.

**Effect Styles:**
- `Shadow/SM`, `Shadow/MD`, `Shadow/LG`, `Shadow/XL`
- `Shadow/Color Violet`, `Shadow/Color Teal`, `Shadow/Color Coral`
- `Blur/Background Blob` (80px layer blur)
- `Blur/Grain Overlay`

**Grid Styles:**
- `Layout/Desktop` — 12 column, 32px margin, 20px gutter, 1200px max
- `Layout/Tablet` — 8 column, 24px margin, 16px gutter
- `Layout/Mobile` — 4 column, 16px margin, 16px gutter

### 14.4 Component Variant Structure

Each component should use Figma's component properties and variants:

**Button:**
- Property: `Variant` = Primary / Secondary / Ghost / Destructive / CTA Gradient
- Property: `State` = Default / Hover / Active / Focus / Disabled
- Property: `Size` = SM (32px) / MD (40px) / LG (48px)
- Property: `Icon` = None / Left / Right / Only
- Property: `Theme` = Light / Dark

**Input:**
- Property: `State` = Default / Focus / Error / Disabled / Filled
- Property: `Type` = Text / Textarea / Search / Select
- Property: `Label` = Yes / No
- Property: `Helper Text` = None / Default / Error

**Card (Integration):**
- Property: `Status` = Connected / Error / Disconnected
- Property: `Accent Color` = Coral / Yellow / Violet / Teal
- Property: `Hover` = Yes / No

**Badge:**
- Property: `Variant` = Success / Error / Warning / Info / Disconnected / Neutral

**Tab:**
- Property: `State` = Default / Hover / Active / Focus

### 14.5 Auto Layout Settings

| Component | Direction | Padding | Gap | Alignment |
|---|---|---|---|---|
| Nav bar | Horizontal | `14px 32px` | `4px` between items | Center vertically |
| Tab bar | Horizontal | `0` | `8px` | Center vertically |
| Card | Vertical | `24px` | `0` (manual spacing) | Stretch horizontally |
| Card header | Horizontal | `0` | `14px` | Center vertically |
| Card actions | Horizontal | `16px 0 0 0` (top padding) | `8px` | Stretch |
| Button | Horizontal | `10px 16px` | `6px` (if icon) | Center both |
| Badge | Horizontal | `3px 14px` | `0` | Center both |
| Input | Vertical | `0` | `4px` (label to input to helper) | Stretch |
| Chat bubble | Vertical | `16px 20px` | `0` | — |
| Bottom bar | Horizontal | `12px 32px` | Space between | Center vertically |

### 14.6 Handoff Checklist

Before marking components as "ready for dev":

- [ ] All color fills use Figma variables (not hard-coded hex)
- [ ] All text uses shared text styles
- [ ] All spacing uses auto layout with variable references
- [ ] All shadows use effect styles
- [ ] Light and dark mode variants both reviewed
- [ ] All interactive states documented (Default, Hover, Active, Focus, Disabled)
- [ ] Contrast ratios verified with accessibility plugin (7:1 minimum for normal text)
- [ ] Component description added explaining usage and behavior
- [ ] Animation notes added as component description or sticky notes (Figma doesn't animate, so document transitions as text)
- [ ] Responsive behavior documented (how component adapts at each breakpoint)

### 14.7 Figma Make-Specific Notes

When using this document with Figma Make:

1. **Token Import:** Figma Make can consume the CSS custom properties section directly. Export the `:root` block as the primary token source.

2. **Component Naming:** Use the `/` separator convention for Figma component names. Example: `Button/Primary/Default`, `Input/Text/Focus`, `Card/Integration/Connected`.

3. **Boolean Properties:** For toggles like "Has Icon" or "Show Helper Text", use Figma boolean properties rather than separate variant values.

4. **Instance Swapping:** Integration card icons should be set up as an instance-swap property pointing to an icon component set, allowing easy swapping between emoji and SVG versions.

5. **Background Effects:** The blob background and grain overlay should be built as a separate "Background" component placed behind page content. This keeps it reusable across layouts without duplicating the blob configuration.

6. **Rainbow Gradient Border:** Since Figma doesn't natively support `border-image` gradients, implement as a frame with the gradient fill, with inner content using negative margin or inner padding to simulate the border. Alternatively, use a thin auto-layout frame as a "divider" component with the gradient fill.

7. **Rotation Transforms:** For the playful rotation effects (logo at -3°, active tabs at -1°, help button at 6°), apply these directly in Figma's rotation field. These are NOT hover-only — they are part of the resting state for these specific elements.

8. **Highlight Underline on Titles:** Build as a nested auto-layout: a text layer on top of a `yellow-200` rectangle (12px height, `radius-sm`, rotated -0.5°). Group these as a "Highlighted Title" component.

---

## Appendix: Design Decision Log

### Core Design Decisions

| Decision | Rationale |
|---|---|
| Plus Jakarta Sans unified typography (v2.0) | Geometric sans with warmth used for all text creates consistency and professionalism. More personality than Inter, less playful than Nunito. Good x-height for readability. Replaced Fraunces in v2.0 rebalance. |
| Cooler color palette (v2.0) | Blues, slate, deep purples, and amber replace the original warm coral/pink-dominant scheme. Creates a more balanced, professional aesthetic suitable for broader audiences while maintaining joyful personality. |
| 5-color brand palette | Blue (trust, professionalism) + Violet (sophistication) + Teal (success) + Amber (energy) + Slate (neutral balance). Each serves a specific emotional purpose. |
| Rotation micro-interactions | Creates a "pinned to a board" or "casually placed" feeling that reinforces the human, non-corporate tone. |
| Emoji for integration icons | Instantly recognizable, cross-platform, adds warmth. Unlike SVG brand logos, they don't require licensing. |
| Dashed card action dividers | Softer than solid lines. Feels more approachable and hand-drawn, consistent with the Soft Maximalism ethos. |
| Rainbow gradient borders | The signature visual element. Immediately differentiates KEN-E from every other SaaS product. Updated colors in v2.0 to match cooler palette. |
| AAA contrast compliance | Higher contrast improves readability and signals that we care about our users' comfort. Essential for professional tools. |
| Refined easing curves (v2.0) | The `ease-bounce` cubic-bezier reduced from 1.56 to 1.2 overshoot creates subtle personality without being overly playful. Professional yet warm. |
| Moderated border radii (v2.0) | Reduced from highly rounded (md: 14px, xl: 24px) to more moderate values (md: 8-10px, xl: 16px) for a more professional appearance while maintaining friendly character. |

### Version 2.0 Rebalance Summary

**Date:** February 14, 2026

**Changes Made:**
1. **Color Palette:** Complete shift from warm coral/pink tones to cooler blues, slate, deep purples, and amber
2. **Typography:** Unified to Plus Jakarta Sans throughout (removed Fraunces entirely)
3. **Border Radii:** Moderated across all components for more professional feel
4. **Animations:** Reduced bounce (1.56 → 1.2) and spring (1.275 → 1.1) overshoot for subtlety
5. **Theme Toggle:** Reversed icon logic - moon (slate-500) in light mode, sun (amber-400) in dark mode
6. **Status Indicators:** Reduced shadow from 8px to 4px blur for refined appearance
7. **Grain Texture:** Reduced opacity from 0.03/0.05 to 0.02/0.04 for cleaner look

**Preserved Elements:**
- Signature rainbow gradient borders (colors updated)
- Playful rotation micro-interactions
- "Soft Maximalism" philosophy and controlled abundance
- WCAG AAA accessibility compliance
- Background blob atmospheric effects
- Card accent color system
- Joyful, personality-driven interactions

**Rationale:** The v2.0 rebalance addresses feedback that the original design was overly feminine by introducing cooler tones, unified professional typography, and more subtle animations, while preserving the signature playfulness and joy that makes KEN-E unique.