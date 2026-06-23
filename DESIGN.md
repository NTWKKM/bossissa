# NTWKKM Design System & Guidelines (DESIGN.md)

*Last Updated: 2026-05-28*

This document serves as the **core design guideline** for any AI agent or developer modifying or creating new interfaces for the NTWKKM project. All UI implementations MUST adhere strictly to these principles to maintain a cohesive, premium, and modern aesthetic across all modules (`index`, `blog`, `tracking`, `fray`).

## 1. Core Philosophy
- **Modern & Premium**: Clean lines, subtle gradients, and glassmorphism. Avoid flat, lifeless components.
- **Cognitive Clarity**: Interfaces must be data-dense but highly readable. Use typography, varied font weights, and spacing to create clear visual hierarchies.
- **Interactive & Alive**: Elements should respond to user interaction. Use hover lifts, border color changes, and smooth transitions to make the UI feel reactive.
- **Dark Mode First-Class**: Every component must look stunning in both Light (`data-theme="light"`) and Dark (`data-theme="dark"`) modes. Always rely on CSS variables.

## 2. Typography
We use a multi-font stack to separate prose, Thai text, and technical data:
- **Primary Text (UI & English Prose)**: `Inter`, -apple-system, sans-serif
- **Secondary Text (Thai Language)**: `Sarabun`
- **Technical Data (Metrics, Logs, IDs, Status, Barcodes)**: `JetBrains Mono`, `Courier New`, monospace (or `SF Mono`)

*Rule of thumb*: Use Monospace for any number, metric, barcode, ID, or system status. Use uppercase with wide letter-spacing (`letter-spacing: 0.05em` to `0.1em`) for small sub-headers or labels.

## 3. Color Palette & CSS Variables
All colors MUST be referenced via CSS variables defined in `:root` and `[data-theme="dark"]`. **Do not hardcode HEX or RGB values** in component styles.

**Brand Colors:**
- `--primary`: Blue (`#2563eb` light / `#60A5FA` dark)
- `--accent`: Red (`#E63946` light / `#F87171` dark)
- **Gradient Text**: Brand titles use a gradient clip: 
  `background: linear-gradient(90deg, var(--primary), var(--accent)); -webkit-background-clip: text; color: transparent;`

**Surface Colors:**
- `--bg-body`: App background (`#F3F4F6` light / `#0F172A` dark)
- `--bg-card`: Card/Panel background (`#FFFFFF` light / `#1E293B` dark)
- `--bg-surface`: Slightly offset background for inner blocks (`#F9FAFB` light / `#0F172A` dark)

**State Colors (Vitals/Status):**
- **OK/Green**: `--state-ok` 
- **Warning/Amber**: `--state-warn` 
- **Error/Red**: `--state-err` 
- **Neutral/Gray**: `--state-neutral` 
*(Use `--state-*-bg` and `--state-*-border` for translucent backgrounds/borders on badges).*

## 4. UI Components & Patterns

### 4.1. Cards & Panels
Cards are the fundamental building block of the UI.
- **Border Radius**: `--radius: 16px` for outer cards, `--radius-sm: 8px` for inner elements.
- **Borders**: `1px solid var(--border)`.
- **Shadows**: Default to `--shadow`.
- **Hover State**: Interactive cards MUST lift on hover (`transform: translateY(-2px)` or `-4px`), increase shadow to `--shadow-hover`, and border color should transition to `var(--primary)`.
- **Decorative Edge**: Consider using a left-edge pseudo-element (`::before`) colored with an accent or state color to give cards a physical feel (e.g., used in tracking cards and papers).

### 4.2. Glassmorphism Headers
- Headers use a blurred backdrop for a premium feel.
- `backdrop-filter: blur(10px)` combined with a semi-transparent background (e.g., `background: color-mix(in srgb, var(--bg-card), transparent 10%)`).
- Positioned as `sticky` at the top with `z-index: 100`.

### 4.3. Badges and Chips
Used extensively for statuses (e.g., `[OK]`, `[Delivered]`, `[Warning]`).
- Small uppercase text (`0.68rem - 0.75rem`), bold weight (`600-700`).
- Monospaced font (`JetBrains Mono`).
- Rounded corners (`border-radius: 999px` or `4px` depending on context).
- Solid border + translucent background. Example:
  `background: var(--state-ok-bg); color: var(--state-ok); border-color: var(--state-ok-border);`

### 4.4. Buttons & Controls
- **Standard Button**: White/Dark background, border, subtle shadow. Hovers to `--primary` border and text.
- **Primary Button**: Solid `--primary` background, white text, bold. Lifts on hover.
- **Pill Shape**: Standard buttons generally use `border-radius: 50px`.

### 4.5. Skeleton Loading
Always implement skeleton loaders for async data to prevent layout shift.
- Use a base background with a gradient overlay animated via `@keyframes shimmer`.

## 5. Animations & Micro-interactions
Motion makes the UI feel alive. Do not create static, rigid interfaces.
- **Entry**: Use `@keyframes fadeUp` (`opacity: 0; transform: translateY(16px)`) for elements entering the DOM. Stagger children using animation delays (`.d1`, `.d2`, etc.).
- **Hover**: Transitions should be smooth (e.g., `transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)` for bouncy effects, or just `ease`).
- **Progress Bars**: Width transitions should be smooth (`transition: width 0.8s ease`).

## 6. Accessibility & Responsiveness
- **Responsive**: Use CSS Grid and Clamp (`clamp(min, val, max)`) functions for fluid typography and layouts. Ensure the layout gracefully stacks to a single column on mobile screens (`max-width: 768px`).
- **Hidden Text**: For icon buttons on mobile, hide text spans rather than removing them completely to maintain screen-reader accessibility.

## 7. AI Agent Instruction Checklist
**When prompting an AI to build a new component or page, strictly enforce these rules:**
1. [ ] "Use CSS variables from the theme root (`var(--primary)`, `var(--bg-card)`, etc.). Do not hardcode colors."
2. [ ] "Use `Inter` for standard text and `JetBrains Mono` for data/metrics."
3. [ ] "Implement hover lift effects (`translateY`) and shadow increases on interactive cards/buttons."
4. [ ] "Ensure compatibility with both `[data-theme="light"]` and `[data-theme="dark"]`."
5. [ ] "Add `fadeUp` entry animations for a smooth loading experience."
6. [ ] "Ensure mobile responsiveness using CSS Grid and flexbox."
