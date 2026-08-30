# UI/UX SYSTEM — SiteSync AI

## Product Identity

SiteSync AI is a **professional construction project intelligence platform**.

It is not a chatbot. It is not a generic AI dashboard. It is not a consumer app.

Every design decision must reinforce the identity of a serious, purpose-built tool used by construction professionals.

---

## Theme

- **Light theme only.** No dark mode.
- Clean, high-contrast, professional.
- Construction-specific — not tech-startup, not generic SaaS.

---

## Color Principles

- Use a **restrained, professional palette**.
- Primary: a single strong accent color (to be defined in Phase 1 design tokens).
- Neutrals: grays for backgrounds, borders, and secondary text.
- Status colors: clearly differentiated for AI confidence levels (high / medium / low), approval states (approved / rejected / pending), and variance states (on-track / at-risk / delayed).
- **No excessive gradients.**
- **No neon or vibrant decorative colors.**
- Colors must communicate **meaning**, not decoration.

---

## Typography

- Use a professional, readable sans-serif typeface (to be defined in Phase 1).
- Consistent type scale: heading, subheading, body, label, caption.
- No decorative fonts.
- No oversized or undersized text for decoration.

---

## Layout

- Clean, structured grid layout.
- Clear visual hierarchy on every screen.
- Tables and lists are the primary data display mechanism — not cards for data tables.
- Dense-but-readable information density appropriate for professional use.
- **Responsive**: desktop first, tablet supported.

---

## Component Rules

- Use **shadcn/ui** components as the base.
- Do not introduce additional component libraries.
- Customizations are made via Tailwind config and CSS variables — not by overriding library internals.
- Every interactive element must have a clear visual state: default, hover, active, disabled, focus.

---

## Prohibited Patterns

The following are explicitly prohibited in SiteSync AI:

| Prohibited | Reason |
|---|---|
| AI avatar or robot icon | Not a chatbot |
| Chatbot-style interface | Wrong product identity |
| Generic "AI Dashboard" layout | No meaning in construction context |
| Excessive glassmorphism | Reduces professional credibility |
| Excessive animations or transitions | Distracting in professional tools |
| Floating action buttons as primary actions | Inappropriate for data-heavy tools |
| Confetti, celebration animations | Inappropriate in construction PM context |
| Placeholder screens | Every screen must have a clear purpose |
| Dark theme | Light theme only |
| Redundant or decorative screens | No unnecessary screens |

---

## Required Patterns

| Pattern | Rule |
|---|---|
| Confidence display | AI confidence score must always be visible on recommendations |
| Evidence display | Evidence (field text that drove AI match) must be accessible |
| Planner action clarity | Approve / Reject / Modify must always be clearly actionable |
| Audit trail | Every decision must be traceable to a user and timestamp |
| Empty states | All empty states must have a clear message and appropriate action |
| Error states | All error states must clearly describe the problem and recovery action |
| Loading states | Loading states must be explicit, not silent |

---

## Accessibility

- WCAG AA target for all planner-facing screens.
- All interactive elements are keyboard navigable.
- Color alone is never the sole indicator of state (always paired with icon or text).
- Sufficient color contrast for all text.
- Form inputs have visible labels.

---

## Screen Design Rules

- **Every screen must have a clear purpose.** If a screen's purpose cannot be stated in one sentence, redesign it.
- **No vanity screens.** No landing pages, splash screens, or decorative intros within the app.
- Navigation must be consistent and predictable.
- The planner review screen is the most critical screen — it must be optimized for speed, clarity, and error prevention.

---

## Voice and Tone (UI copy)

- Professional and direct.
- Construction terminology is preferred over generic tech terminology.
- "Activity" not "task". "Schedule" not "timeline". "Approved Actual" not "confirmed data".
- No marketing language inside the app.
- Error messages are clear and actionable, not apologetic or vague.
