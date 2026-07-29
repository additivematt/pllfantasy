---
name: styla
description: Design system guide defining color tokens, glassmorphism CSS, Plotly layouts, and tooltip patterns for all PLL Fantasy UIs.
---

# Styla: The Obsidian Design System

This document defines the visual language and UI patterns for all web applications in the PLL Fantasy workspace. Adhering to these standards ensures a premium, cohesive user experience across all tools (Interrogator, Predicta, etc.).

---

## 1. Core Color Palette

| Usage | Color Name | Hex Code | Purpose |
| :--- | :--- | :--- | :--- |
| **Background** | Deep Obsidian | `#0b0e14` | Primary app background. |
| **Surface** | Card BG | `#161b22` | Background for cards and headers. |
| **Primary Accent**| Electric Purple | `#9f7aea` | Main branding, headings, and active outlines. |
| **Secondary Accent**| Vibrant Gold | `#ecc94b` | Key highlights and secondary stat values. |
| **Border** | Muted Grey | `#30363d` | Subtle borders and dividers. |
| **Text (Primary)** | Off-White | `#f0f6fc` | High-readability body text. |
| **Text (Secondary)**| Slate Blue | `#8b949e` | Labels and less important metadata. |

---

## 2. Matchup & Performance Scale (Functional Colors)

When visualizing matchup quality or historical performance, use an explicit Red-to-Green scale for consistency.

*   **Positive (Success)**: `#1a9850` (Deep Green)
*   **Neutral (Baseline)**: `#ffffbf` (Pale Yellow/Tan)
*   **Negative (Tough)**: `#d73027` (Deep Red)

---

## 3. Visual Patterns

### Glassmorphism
Interactive elements should feel "layered" over the obsidian background.
*   **Property**: `backdrop-filter: blur(10px);`
*   **Background**: `rgba(255, 255, 255, 0.05)` or `rgba(22, 27, 34, 0.9)` for overlays.
*   **Border**: `1px solid rgba(255, 255, 255, 0.1)` (default) or `var(--accent)` (highlighted).

### Premium Tooltips
Never use default browser or library tooltips.
*   **Style**: Custom HTML `div` with absolute/fixed positioning.
*   **Layout**: Bold header (`Electric Purple`), followed by labeled stat rows.
*   **Shadow**: `box-shadow: 0 10px 30px rgba(159, 122, 234, 0.2);`
*   **Interaction**: Mobile/Tablet friendly. Tapping a data point opens and locks the tooltip. Tapping anywhere else on the screen (background, other elements, or empty chart space) dismisses it. Do not use explicit "✕" close buttons.
*   **Inter-App Deep-Linking**: Action buttons within tooltips (such as "Open Interrogator ↗") use glassmorphism borders (`1px solid rgba(159, 122, 234, 0.4)`), Electric Purple accents, and `target="_blank"` navigation with `event.stopPropagation()` to prevent unwanted canvas dismissals.

### Interactive Charts (Plotly)
*   **Background**: `rgba(0,0,0,0)` (Transparent).
*   **Titles**: Upper-case, bold, and colored with `Electric Purple`.
*   **Gridlines**: Muted (`#30363d`).
*   **Axes**: White or light grey labels; remove zerolines where possible for a cleaner look.

### Interactive Charts (Chart.js)
Chart.js is used for continuous career trend visualizations (e.g. in Interrogata). Style components as follows:
*   **Fonts**: Global default font family set to `'Inter', sans-serif`, color to `--text-secondary` (`#8b949e`), size `11px`.
*   **Grids**: Gridlines colored with `--border` (`#30363d`). Set zero-lines to transparent or same color.
*   **Legends/Tooltips**: Render legends/labels with secondary slate color. Custom tooltips must use Card BG (`#161b22`), rounded borders (`6px`), and Electric Purple (`#9f7aea`) accents.

---

## 4. Typography & Branding

### General Typography
*   **Font Family**: `Inter`, sans-serif (Google Fonts).
*   **Weights**: 400 (Regular), 700 (Bold). (Avoid 900 for a cleaner look).

### Logo & Header Style
*   **Header Layout**: Center-justified (`flex-direction: column`, `align-items: center`).
*   **Top Offset**: Mandatory `3rem` from the top of the viewport.
*   **Logo Structure**: Single-row layout: `[PLL] [APP NAME] [Subtitle]`.
*   **Font Size**: Logo text (`1.5rem`), Subtitle (`0.85rem`).
*   **PLL Styling**: Electric Purple (`#9f7aea`), 700 weight, uppercase.
*   **App Name Styling**: Off-White (`#f0f6fc`), 700 weight, uppercase.
*   **Subtitle**: Slate Blue (`#8b949e`), 500 weight, uppercase, letter-spaced (1px).
*   **Separator**: Use a vertical line (`border-left: 1px solid var(--border)`) on the subtitle with `padding-left: 12px` and `margin-left: 4px`.

---

## 5. Responsive Layouts & Breakpoints

To ensure premium looks on both mobile/tablet couch-viewing and desktop analysis:
*   **Breakpoints**:
    *   **Desktop**: Viewports `>= 1024px`. Multi-column layouts (e.g. `2fr 1fr` grids).
    *   **Mobile / Portrait Tablet**: Viewports `< 768px`. Collapse all grids to `1fr` single-column layout.
*   **Touch Friendly Targets**: Buttons, dropdown selections, and interactive nodes must have a minimum tap target of `44px x 44px`.
*   **Spacing Adaptability**: Responsive padding variables:
    ```css
    :root {
        --padding-desktop: 1.5rem;
        --padding-mobile: 1rem;
    }
    ```

---

## 6. Micro-Animations & CSS Timings

*   **Transitions**: Smooth out hover scales, border colors, and background shifts using a unified timing:
    `transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);`
*   **Flash Highlights**: When selecting a player card that focuses a chart node (or vice versa), apply a temporary pulsing border:
    ```css
    @keyframes node-flash {
        0% { border-color: var(--border); box-shadow: 0 0 0 rgba(159, 122, 234, 0); }
        50% { border-color: #ff007f; box-shadow: 0 0 15px rgba(255, 0, 127, 0.6); }
        100% { border-color: var(--accent); box-shadow: 0 0 0 rgba(159, 122, 234, 0); }
    }
    ```

---

## 7. Implementation Example (CSS Variables)
```css
:root {
    --bg-color: #0b0e14;
    --card-bg: #161b22;
    --text-primary: #f0f6fc;
    --text-secondary: #8b949e;
    --accent: #9f7aea;
    --accent-secondary: #ecc94b;
    --border: #30363d;
    --success: #1a9850;
    --danger: #d73027;
    --transition-standard: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improvements_and_baselines/SKILL.md) skill. Do not add new improvement ideas to this file.
