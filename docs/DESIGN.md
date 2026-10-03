# DESIGN.md: PitchPrep

> Place this file in `docs/DESIGN.md` (or the repo root). It is the visual and interaction spec for the frontend. `AGENTS.md` and `docs/PRD.md` still apply. Behavior and scope come from the PRD; look, feel, and motion come from this file.

## 0. How to use this file

- The look is derived from a reference landing-page video Hamza supplied (a data-platform product site). **Borrow the visual language only.** Do not copy its brand name, copy, icons, emoji, logos, pricing, or statistics. Everything on screen is PitchPrep's own: our words, our icons, our domain.
- Before building UI, read the installed design skills in `.agents/skills/` (Taste Skill and the Emil Kowalski skill) as `AGENTS.md` requires.
- **Precedence:** this file decides brand decisions (palette, type, shapes, section structure, copy tone). The skills decide craft quality (spacing rigor, motion timing, accessibility checks, pre-flight). If a skill rule conflicts with a brand decision here, keep the brand decision, apply the skill everywhere else, and mention the conflict in your summary.
- The reference video shows the site inside a rounded device frame on a grey canvas. That is presentation only. **Do not build the frame.** The site is full-width.

## 1. Design intent

PitchPrep should feel **clean, confident, and trustworthy**, like a precise instrument for people who sell. The page is mostly calm off-white with strong black type, one warm accent (yellow highlight), one action color (blue), and one playful accent (hot pink) used in tiny doses. A dark section near the end gives the page a strong rhythm change.

Personality words: precise, bright, approachable, evidence-first.

Anti-goals: generic purple gradients, stock "AI brain" imagery, dense dashboards on the landing page, glassmorphism everywhere, fake social proof.

## 2. Reference analysis (what the video shows)

| Template section | What it does | PitchPrep equivalent |
|---|---|---|
| Floating pill nav on off-white | Logo pill + link pill + search + language + black CTA | Logo pill + link pill + black CTA pill (no search, no language switcher) |
| Hero: huge black headline, one phrase on a yellow highlight, small grey subline, centered blue button, five floating isometric white tiles each holding a colored glyph | Establishes brand and the primary action | Hero with centered button; five tiles represent the pipeline stages |
| Intro slide: left-aligned big headline, subline, right side concentric circles with small floating icon "orbs" | Product statement | Optional "what it is" band (see section 6.2) |
| Yellow pill label ("Features") above a centered headline, then two large white rounded cards, each with a mini UI mockup and a short title and caption | Feature explanation | Two feature cards with **real HTML mockups** of PitchPrep UI |
| Blue root node with a connector tree to white child cards, each with a blue dot | Explains the workflow | Pipeline tree: root plus six stage cards |
| Dark section, giant white headline with one phrase on yellow, soft dark blob shapes with a pink dot in each corner | Emotional/stat moment | Dark "trust" statement section (no invented numbers) |
| Dark pricing cards with glowing borders, round icon badges, tilted in 3D | Pricing | **Not used.** PitchPrep has no pricing in the MVP |
| Dark closing: nav pill reappears, big pill panel with yellow dots flanking "Get free demo", small social tiles | Final CTA and footer | Dark closing CTA panel with our button label, footer links |

## 3. Design tokens

Define these as CSS variables (Tailwind theme extension). Values marked *(sampled)* were measured from the video; others are chosen for PitchPrep.

### 3.1 Color

**Surfaces (light)**
| Token | Value | Use |
|---|---|---|
| `--bg` | `#F9F9F9` *(sampled)* | Page background |
| `--surface` | `#FFFFFF` *(sampled)* | Cards, tiles, nav pill |
| `--line` | `#E7E7EA` | Hairline borders, connector lines |
| `--ink` | `#0C0C0C` *(sampled)* | Headlines, primary text |
| `--ink-muted` | `#5B5B63` | Body copy (6.4:1 on `--bg`) |
| `--ink-subtle` | `#6B6B73` | Captions (5.0:1 on `--bg`, minimum for small text) |

**Surfaces (dark section)**
| Token | Value | Use |
|---|---|---|
| `--dark-bg` | `#0D0D0D` *(sampled)* | Dark section background |
| `--dark-surface` | `#1F1F1F` *(sampled)* | Dark cards, blobs |
| `--dark-line` | `#2C2C2E` | Borders on dark |
| `--on-dark` | `#FFFFFF` | Headlines on dark |
| `--on-dark-muted` | `#A1A1AA` | Body on dark (6.4:1 on `--dark-surface`) |

**Brand and accents**
| Token | Value | Use |
|---|---|---|
| `--highlight` | `#F7DA36` *(sampled, yellow)* | Headline highlight, label pills, small dots. Always paired with `--ink` text (14:1) |
| `--action` | `#1F6BE8` | Primary buttons, root node, links on light. **Deliberately deeper than the template's `#287AF8`**, which only reaches 4.0:1 with white text; this reaches 4.85:1 |
| `--action-hover` | `#1B63D6` | Hover/pressed (5.5:1 with white) |
| `--pop` | `#F3158C` *(sampled, pink)* | Tiny accents only: a dot, a tile glyph, a progress marker. Never body text, never a large fill. As text on white it is only 3.96:1 |

**Status (added; the template has no equivalent)**
| Token | Value | Use |
|---|---|---|
| `--verified` | `#15803D` on `#DCFCE7` | "Verified" claim badge |
| `--caution` | `#92400E` on `#FEF3C7` | "Limited data" badge, flagged claims |
| `--error` | `#B42318` on `#FEE4E2` | Errors |

Rules:
- Yellow is a highlight, not a background for large areas. **One highlighted phrase per heading, one highlighted heading per section at most.**
- Pink appears at most a few times per screen.
- Status is never shown by color alone: always include an icon and a text label.
- Dark mode: the page is light by default. The dark section is a design feature, not a theme. Add a full dark theme only if the design skills require it; if so keep token parity and re-verify contrast.

### 3.2 Typography

The template uses a rounded geometric sans with a confident bold weight (it resembles Gilroy/Outfit; the exact font could not be identified from video). Use a free equivalent through `next/font/google`:

- **Primary:** Use Outfit. This is a brand decision and is not overridden by the skills. If the Taste Skill objects, note it in your summary and keep Outfit.
- **Mono (code/URLs/source chips):** `JetBrains Mono` or `Geist Mono`, used sparingly.

| Role | Size (fluid) | Weight | Tracking | Line height |
|---|---|---|---|---|
| Hero headline | `clamp(2.5rem, 7vw, 5.5rem)` | 700 | -0.03em | 1.04 |
| Section headline | `clamp(2rem, 4.5vw, 3.5rem)` | 700 | -0.025em | 1.08 |
| Card title | 1.25 to 1.5rem | 600 | -0.01em | 1.2 |
| Body | 1rem to 1.125rem | 400 | 0 | 1.55 |
| Caption / label | 0.75 to 0.875rem | 500 | 0 | 1.4 |

Headlines are centered on the hero and section intros, left-aligned inside cards and the app UI. Keep headlines to two lines on desktop.

**Highlight treatment:** a rectangle of `--highlight` behind the key phrase, `border-radius: 0.2em`, horizontal padding `0.15em`, no rotation, no gradient. Implement with an inline `<mark>`-style element with transparent default styling overridden. Text stays `--ink`.

### 3.3 Shape, spacing, depth

- **Radius:** buttons 10px; small cards and chips 14px; large cards 24px; label pills and nav pill fully rounded; tiles 20px.
- **Spacing:** 4px base grid. Section vertical padding `clamp(4rem, 10vw, 8rem)`. Content max width 1200px; text blocks max 65ch.
- **Borders:** 1px `--line`. Cards usually have both a hairline and a soft shadow.
- **Shadows (light):** very soft and layered, low opacity, never harsh. Example: `0 1px 2px rgb(0 0 0 / .04), 0 8px 24px rgb(0 0 0 / .06)`.
- **Dark cards:** `--dark-surface` with a 1px `--dark-line` border and a faint inner glow (`inset 0 1px 0 rgb(255 255 255 / .04)`). Subtle only.
- **Section transitions:** the next section can slide up over the previous one with a large rounded top edge (about 40px radius). Use this once, from the light page into the dark section.

## 4. Components

### 4.1 Navigation pill
- Fixed or sticky, centered, floating with margin from the top. Two pills side by side: logo pill (white, hairline, small shadow) and link pill.
- Links (PitchPrep): **How it works**, **Trust**, **Pipeline**. These scroll to sections on `/`.
- Right side: a black pill button "Let's prep your pitch" (`--ink` background, white text).
- No search, no language switcher, no pricing link.
- Mobile: collapse the links into a menu button; keep the black CTA visible.
- Logo: a simple wordmark "PitchPrep" with a small custom mark. Create an original mark (for example a spark or a checked document corner). Do not reuse the template's mark.

### 4.2 Buttons
- **Primary:** `--action` background, white text, 10px radius, height 44 to 48px, medium weight, optional trailing circled-arrow icon. Hover darkens to `--action-hover`; pressed state scales slightly (see motion).
- **Black pill:** `--ink` background, white text, fully rounded. Used in the nav and the closing panel.
- **Secondary:** white background, hairline border, ink text.
- Every button has a visible keyboard focus ring (2px `--action` with 2px offset).
- Touch targets at least 44px.

### 4.3 Label pill
Small fully rounded pill, `--highlight` background, `--ink` text, 12px medium. Sits above section headlines ("How it works", "Trust", "Pipeline").

### 4.4 Feature card
Large white card, 24px radius, hairline plus soft shadow. Top two thirds: a **mini live-style UI mockup built in HTML/CSS** (not an image). Below: centered title and a two-line caption in `--ink-muted`. Content fades toward the card's bottom edge on the mockup, as in the template.

### 4.5 Isometric tile (hero)
White rounded square rotated into an isometric diamond (rotateX/rotateZ transform), soft ground shadow, one flat colored glyph on top with a slightly offset lower-layer shadow in a tint of the glyph color to suggest depth. Five tiles in a loose arc under the button; the outer two are partly cropped by the viewport.

### 4.6 Pipeline tree
Blue root node, centered, rounded 14px, white text. Elliptical right-angle connector lines (`--line`, 1.5px) drop to a row of white cards; each card has a small blue dot (top-left) and a two-line label. A second row hangs beneath two of the cards. Lines draw in on scroll.

### 4.7 Dark panels
Dark section uses large soft blob shapes (`--dark-surface`) in the four corners, each with a small `--pop` dot. They drift or morph slowly (see motion).

### 4.8 Claim card and verification badge (app only)
- White card, 14px radius, claim text, a source chip showing the domain (mono font) as a link, and a badge: **Verified** (check icon, `--verified`), **Flagged** (alert icon, `--caution`), or **User-provided** (pencil/clipboard icon, neutral).
- Removed claims never render as normal claims; the brief shows an "Evidence limits" note instead.

### 4.9 Progress stepper (app only)
Vertical or horizontal list of the six stages (Parsing, Collecting, Analyzing, Matching, Writing, Verifying). Pending: hollow dot. Active: `--action` dot with a gentle pulse. Done: filled check. Failed: `--error` icon with text. Screen-reader live region announces stage changes.

### 4.10 Form fields (app only)
White input, hairline border, 10px radius, 48px high, visible label above (not placeholder-only). Required fields marked in text ("Required"), not only with an asterisk. Helper text below. The paste box is a larger textarea with a short example hint. Errors appear below the field with an icon and `--error` text.

## 5. Iconography

- **Do not use emoji** and do not reuse the template's glyphs. Use one consistent custom or library icon set (for example Lucide) in a 1.75px stroke, 20 to 24px, rounded joins.
- Hero tile glyphs are larger, flat, two-tone illustrations in `--pop`, `--highlight`, and `--action`, drawn as inline SVG. Suggested subjects, one per pipeline stage:
  1. **Parser:** a text block with a highlighted line
  2. **Collector:** a link/globe with a magnifier
  3. **Analyst:** a spark or chart-with-pin
  4. **Matcher:** two connecting pieces
  5. **Writer + Verifier:** an envelope with a check mark
- Provide meaningful `aria-label`s for informative icons and `aria-hidden` for decorative ones.

## 6. Landing page (`/`)

Matches PRD section 5.1 and the `AGENTS.md` rule: intro-first, centered button, no form on `/`.

### 6.1 Hero
- Nav pill at top.
- Centered headline, for example: **"Walk into every pitch prepared."** with **"prepared"** on the yellow highlight. (Final copy can be tuned; keep it short, concrete, and free of invented claims.)
- One supporting line, for example: "Add a company. PitchPrep researches it, checks every claim against its sources, and drafts your email."
- **One centered primary button:** "Let's prep your pitch" with the circled-arrow icon. It navigates to `/app`.
- Five isometric tiles below, in an arc, entering with a staggered rise.

### 6.2 What it is (optional intro band)
Left-aligned headline and short paragraph, with the concentric-circle orbit graphic on the right: a central document icon ringed by small round "orbs" (source, check, mail). Skip this section if the page is getting long; the next section carries the same idea.

### 6.3 How it works (yellow label: "How it works")
Headline, for example: "From a company name to a sourced brief."
Two large feature cards with real HTML mockups:
1. **"Research that cites itself":** a brief fragment with three claim rows, each with a source chip and a Verified badge. One card slides forward as if picked up (like the template's raised card).
2. **"Works with what you have":** the input panel mockup with the three fields (company name, website or social link, pasted details) and a pasted-listing preview. A toggle-style row can show "Website" vs "Social link".

Mockups are static visuals: not focusable, no real inputs, and `aria-hidden`. Use styled divs, not `<input>` elements.

### 6.4 Pipeline (yellow label: "Pipeline")
Headline, for example: "Six steps. Every claim checked."
Tree with the root node **"PitchPrep pipeline"** and cards in two rows:
- Row 1: **Input Parser**, **Source Collector**, **Analyst**, **Matcher**
- Row 2 (under Analyst and Matcher): **Writer**, **Verifier**
Each card has a one-line plain-language description (for example Verifier: "Checks each claim against its source. Unsupported claims are removed."). Use only facts that are true of the PRD.

### 6.5 Trust (dark section)
Slides up over the light page with a rounded top edge.
- Headline on dark with one yellow-highlighted phrase, for example: "Every claim has a **source**." (Do not use numbers, user counts, or percentages unless they come from real evaluation results in LangSmith. Once real results exist, a single honest metric such as groundedness may appear with its method noted.)
- Short supporting paragraph about verification and "limited data" honesty.
- Corner blobs with pink dots.
- Optionally a compact sample brief on dark cards showing Verified and Flagged badges.

### 6.6 Closing CTA and footer (dark)
- Large dark panel with hairline border, a yellow dot at each end, and our button label as the large type: **"Let's prep your pitch"**. The whole panel is the link to `/app`.
- Footer row: logo pill, short links, and only real external links (for example the project's GitHub repository). Do not add social icons for accounts that do not exist.

### 6.7 Copy rules
- Plain, specific, benefit-led. No filler, no lorem ipsum, no "revolutionary".
- No fake testimonials, customer logos, user counts, ratings, or performance claims.
- Product claims must match what the PRD says the system does.

## 7. App screens (`/app`)

Same tokens and components, calmer layout. Light surface, white cards on `--bg`, black headlines, `--action` for primary actions, yellow only for small label pills. No isometric tiles or dark blobs in the working screens; they belong to the landing page.

- **Seller setup:** one centered card, two fields, a clear Save button.
- **Target input:** card with the three inputs from PRD 5.2, the website/social field in its own required slot with helper text ("Use the company's website. If it has none, use its Instagram, Facebook, or LinkedIn page.").
- **Live progress:** stepper (4.9) beside a short status line. Show an indeterminate state if progress is unknown; never fake percentages.
- **Brief view:** two-column on desktop (brief left, email draft and actions right), single column on mobile. Claim cards (4.8), a "Limited data" caution banner when relevant, editable email in a textarea with Regenerate and Copy actions, thumbs up/down with an optional comment.
- **History:** simple list of cards with company name, date, and status.
- **States:** every screen has designed loading (skeletons, not spinners alone), empty, and error states using the copy in PRD 5.3.

## 8. Motion

Defer to the Emil Kowalski skill for timing and easing details. The intended feel, drawn from the reference video:

| Moment | Behavior |
|---|---|
| Hero entrance | Headline fades up; highlight swipes in left to right behind the key word; tiles rise in with a short stagger |
| Hero tiles | Idle float of a few pixels, slow and out of phase with each other |
| Section reveals | Content translates up a little and fades in once, on first view |
| Feature card mockup | The raised claim card eases forward; toggles in the second card switch once |
| Pipeline tree | Connector lines draw in; cards appear in order from root to leaves |
| Light to dark transition | The dark section slides up over the page with a rounded top edge |
| Dark blobs | Slow morph/drift; pink dots stay fixed to each blob |
| Closing panel text | Masked line reveal of the large label |
| Buttons | Fast color change on hover; slight scale-down on press |
| Progress stepper | Dot pulse on the active stage; check draws on completion |

Rules:
- Animate `transform` and `opacity` only where possible. No layout-shifting animation.
- UI feedback (hover, press, toggles) stays under 200ms. Entrance and reveal animations stay under about 600ms. Use decisive ease-out curves; avoid bouncy easings on functional UI.
- **Respect `prefers-reduced-motion`:** replace movement with simple fades or no animation, and stop idle loops and morphing blobs.
- Never animate things the user does repeatedly while working (typing, editing the email, switching history items) beyond a minimal transition.
- Do not gate content behind animation: all text is in the DOM and readable without JavaScript animation completing.

## 9. Responsive behavior

- Design mobile first from 360px.
- Hero: headline scales fluidly; the button stays centered and full-width on narrow screens; tiles reduce to three and are cropped at the edges.
- Feature cards stack. Pipeline tree becomes a vertical list with a left connector line; the root sits on top.
- Dark section padding reduces; blobs shrink and move partly off-screen.
- Nav collapses to logo plus menu button plus CTA.
- No horizontal page scroll at any width.

## 10. Accessibility

- Text contrast of at least 4.5:1 (3:1 for large text). The tokens above were checked; re-check any new combination.
- Semantic landmarks and one `h1` per page, ordered headings.
- Visible focus states everywhere, logical tab order, skip link to main content.
- Status conveyed by icon plus text, not color alone.
- Mockups inside feature cards are decorative: mark them `aria-hidden` and make sure the same information is available in text.
- Live progress uses an `aria-live` region.
- Forms have labels, error association (`aria-describedby`), and preserve input on error.

## 11. Assets

- Produce all icons and illustrations as inline SVG or from an open icon set. Nothing is copied from the reference video.
- Do not embed screenshots of the reference.
- No stock photos of people. If imagery is needed, use diagrams or UI mockups.
- Fonts via `next/font` (self-hosted at build time), no external font CSS at runtime.

## 12. Do and don't

**Do**
- Keep big black type and generous whitespace.
- Use the yellow highlight once per heading, blue only for actions, pink in tiny doses.
- Build mockups from real components using real product copy.
- Keep the intro-first flow: landing page, then the centered button, then `/app`.

**Don't**
- Don't copy the reference's name, copy, pricing, member counts, or emoji.
- Don't add a pricing section, newsletter form, fake logo wall, or testimonials.
- Don't put the input form or any agent UI on `/`.
- Don't use pink or yellow for body text.
- Don't rely on animation to communicate essential information.

## 13. Pre-flight checklist (run before reporting UI work as done)

- [ ] Palette uses only the tokens above; `--action` is `#1F6BE8`, not the template's lighter blue
- [ ] Headlines have at most one highlighted phrase; pink used sparingly
- [ ] No emoji, no template assets, no invented stats or testimonials
- [ ] Hero has exactly one centered primary button that routes to `/app`
- [ ] No form fields on `/`
- [ ] All states designed: loading, empty, error
- [ ] Verified, Flagged, and User-provided badges each have icon plus text
- [ ] `prefers-reduced-motion` honored; idle animations stop
- [ ] Works at 360px with no horizontal scroll; touch targets at least 44px
- [ ] Contrast checked; focus rings visible; keyboard path works end to end
- [ ] Taste Skill and Emil Kowalski skill checklists run; any conflicts with this file noted
- [ ] `npm run lint` and `npm run build` pass in `frontend/`
