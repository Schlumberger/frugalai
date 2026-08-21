---
version: "1.0"
scope: "copy-generation-only"
audience: "technical, commercial, executive"
intent: >
  This document defines the linguistic rules agents must follow when generating
  user-facing text. It prioritizes clarity, authority, and technical credibility.
  Deviation from these rules is considered a defect, not stylistic freedom.
---

## Core Voice Principles

The voice is:

- **Authoritative** — informed, confident, evidence-driven
- **Technical but accessible** — precise without unnecessary jargon
- **Reserved** — no hype, no theatrics
- **Declarative** — statements over persuasion

Agents must write as if addressing:
> engineers, scientists, executives, and regulators simultaneously.

---

## Default Narrative Stance

- Third person or neutral imperative
- No conversational filler
- No rhetorical questions
- No emotional framing

✅ “The system integrates subsurface data to support decision-making.”  
❌ “Ever wondered how you can make better decisions?”

---

## Sentence Construction Rules

### Length
- Prefer **short to medium sentences**
- One idea per sentence
- Avoid compound marketing sentences

✅ “The workflow reduces uncertainty. It automates validation.”  
❌ “The workflow reduces uncertainty while simultaneously transforming how teams work.”

---

### Grammar & Structure

- Active voice preferred
- Passive voice acceptable for scientific or regulatory contexts
- Avoid adverbs unless technically meaningful

✅ “The model predicts pressure evolution.”  
❌ “The model rapidly and dramatically predicts pressure evolution.”

---

## Vocabulary Control

### Preferred Verbs

Use verbs that imply **capability, support, and enablement**:

- enables
- supports
- integrates
- provides
- applies
- improves
- reduces
- optimizes
- validates
- monitors

---

### Restricted / Discouraged Language

Agents must **not** use:

- Marketing hype:
  - revolutionary
  - game‑changing
  - disruptive
  - cutting‑edge
  - next‑generation
- Emotional or casual phrasing:
  - powerful
  - exciting
  - simple
  - easy
  - seamless
- Anthropomorphism:
  - “the system understands”
  - “the platform thinks”

---

## Technical Precision Rules

- Prefer **specific outcomes** over general claims
- Quantify when data exists
- If uncertain, state constraints explicitly

✅ “Reduces non‑productive time by automating diagnostics.”  
✅ “Results depend on data quality and deployment context.”  
❌ “Delivers unmatched performance.”

---

## UI Microcopy Guidelines

### Buttons & Actions

- Use **verb‑first, neutral phrasing**
- No motivational language

✅ “View results”  
✅ “Run simulation”  
❌ “Discover insights”  
❌ “Get started now”

---

### Labels & Headings

- Nouns over phrases
- Avoid sentence case in headings longer than 3 words

✅ “Production forecast”  
❌ “See how production will change”

---

### Empty States

- Informative, not apologetic
- Explain *what is missing*, not *why the user failed*

✅ “No data available for the selected interval.”  
❌ “You don’t have any data yet.”

---

## Descriptions & Explanatory Text

Structure explanations as:

1. **What it is**
2. **What it does**
3. **Why it matters (optional)**

Example:
> “This model estimates reservoir pressure over time.  
> It integrates historical and simulated data to support planning decisions.”

---

## Scientific & Engineering Tone

When discussing models, algorithms, or workflows:

- Avoid certainty where none exists
- Use “supports”, “informs”, “estimates” rather than “proves” or “guarantees”

✅ “The analysis supports scenario comparison.”  
❌ “The analysis proves the optimal outcome.”

---

## Regulatory & Risk Language

When applicable:

- Use neutral, careful phrasing
- Explicitly acknowledge assumptions and limitations

✅ “Results are subject to operational constraints.”  
✅ “Assumptions are documented in the methodology.”

---

## Formatting Conventions

- Units must follow SI or industry‑standard notation
- Use symbols consistently (%, °C, MPa)
- Avoid emoji, exclamation marks, or stylistic punctuation
- Always use LaTeX style  \( \eta_{H_2} \) and never Unicode equivalents like H₂ 

---

## Do’s and Don’ts Summary

### Do
- Write like a technical report, not an advert
- Assume a global, expert audience
- Favor accuracy over persuasion

### Don’t
- Sell, hype, or entertain
- Use conversational tone
- Introduce humor or personality

---

## Agent Decision Rule (Critical)

When multiple phrasings are possible:

> Choose the version that would be acceptable in a
> **technical review, investor briefing, or regulatory appendix**.

If uncertain, simplify and neutralize.

---

## Example Transformations

**Marketing‑style input**  
> “A powerful platform that revolutionizes subsurface understanding.”

**Approved output**  
> “A platform that integrates subsurface data to support analysis and planning.”

---

End of `LANGUAGE.md`