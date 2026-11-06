---
name: Wealth Management Copilot
description: Incumbent advisor dashboard and Meeting Prep extension
colors: {"bg": "#f5f6f8", "surface": "#ffffff", "surface-2": "#f8f9fb", "surface-hover": "#f0f2f5", "border": "#e2e5ea", "border-subtle": "#ebedf1", "text": "#1a1f2e", "text-2": "#3d4556", "text-3": "#6b7280", "text-4": "#9ca3af", "accent": "#3563e9", "accent-soft": "rgba(53, 99, 233, 0.08)", "accent-medium": "rgba(53, 99, 233, 0.15)", "green": "#16a34a", "green-soft": "rgba(22, 163, 74, 0.08)", "amber": "#ca8a04", "amber-soft": "rgba(202, 138, 4, 0.06)", "red": "#dc2626", "red-soft": "rgba(220, 38, 38, 0.06)", "violet": "#7c3aed", "violet-soft": "rgba(124, 58, 237, 0.06)", "teal": "#0d9488", "teal-soft": "rgba(13, 148, 136, 0.06)"}
typography: {"headline": {"fontFamily": "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "fontSize": "22px", "fontWeight": 700, "letterSpacing": "-0.02em"}, "section-title": {"fontFamily": "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "fontSize": "13px", "fontWeight": 700}, "item-title": {"fontFamily": "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "fontSize": "12.5px", "fontWeight": 600}, "body": {"fontFamily": "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "fontSize": "12.5px", "fontWeight": 400, "lineHeight": 1.55}, "label": {"fontFamily": "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "fontSize": "12px", "fontWeight": 500}, "metadata": {"fontFamily": "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", "fontSize": "11.5px", "fontWeight": 400}, "mono": {"fontFamily": "'JetBrains Mono', 'SF Mono', monospace", "fontSize": "11.5px"}}
rounded: {"sm": "6px", "nav": "8px", "md": "10px", "lg": "14px", "reference": "3px"}
spacing: {"xs": "4px", "sm": "8px", "md": "12px", "lg": "16px", "xl": "20px", "xxl": "24px"}
components: {"button-primary": {"backgroundColor": "{colors.accent}", "textColor": "{colors.surface}", "rounded": "{rounded.sm}", "padding": "8px 13px"}, "button-secondary": {"backgroundColor": "{colors.surface}", "textColor": "{colors.text-2}", "rounded": "{rounded.sm}", "padding": "8px 13px"}, "field": {"backgroundColor": "{colors.surface}", "textColor": "{colors.text}", "rounded": "{rounded.sm}", "padding": "9px 10px"}, "card": {"backgroundColor": "{colors.surface}", "rounded": "{rounded.md}"}, "chip-accent": {"backgroundColor": "{colors.accent-soft}", "textColor": "{colors.accent}", "rounded": "{rounded.sm}", "padding": "3px 9px"}, "nav-active": {"backgroundColor": "{colors.accent-soft}", "textColor": "{colors.accent}", "rounded": "{rounded.nav}", "padding": "8px 12px"}, "reference": {"backgroundColor": "{colors.accent-soft}", "textColor": "{colors.accent}", "rounded": "{rounded.reference}", "padding": "2px 4px"}}
---
# Design System: Wealth Management Copilot

## Overview

**Creative North Star: "The Advisor Workspace"**

The existing advisor dashboard is a compact working interface: DM Sans, white cards on a cool gray canvas, fine borders and blue actions. Meeting Prep extends this vocabulary inside the current sidebar and topbar. Its brief reads as a structured document, with evidence kept alongside the text.

Scope: incumbent web UI tokens and the Meeting Prep extension. This is a record of the shipped implementation, not a replacement identity. Evidence: `dashboard/src/index.css`, `dashboard/src/meeting-prep.css`, `dashboard/src/MeetingPrep.jsx` and its integration in `dashboard/src/App.jsx`; desktop and mobile renders were inspected.

**Key Characteristics:**

- Compact typography and restrained spacing.
- White surfaces separated by subtle borders.
- Blue actions, navigation selection and source references.
- Visible draft, review and synthetic-data states.

## Colors

A cool neutral foundation carries a single blue action accent and small semantic status accents. Frontmatter retains the source token names and color formats; white also serves the incumbent raised background.
### Primary

- **Action Blue** (`accent`): primary buttons, selected navigation, priority numbers and source links. `accent-soft` fills selected navigation and reference chips; `accent-medium` strengthens selected references and text selection.
### Secondary

- **Status Green / Amber / Red**: gains and reviewed states, attention and draft states, losses and errors. Pair with explicit labels. Meeting Prep darkens green chip text to `#117334` and amber chip text to `#865800` on their existing soft fills.
- **Category Violet / Teal**: incumbent categories; violet also labels the Meeting Brief. Soft variants support compact chips rather than large decorative fields.
### Neutral

- **Canvas / White Surface / Quiet Surface** (`bg`, `surface`, `surface-2`): page background, cards and controls, then source-record/message interiors.
- **Hover Surface** (`surface-hover`): secondary button and table-row feedback.
- **Border / Subtle Divider** (`border`, `border-subtle`): controls versus card outlines and internal separators.
- **Ink / Secondary Ink / Muted Ink / Faint Ink** (`text` through `text-4`): headings, working content, supporting information, and inherited low-emphasis dashboard metadata. Faint ink is not a prescription for new essential text.

**The Blue Action Rule.** Use blue for actionable emphasis and selection; reserve semantic colors for status and categorization.

## Typography

**Heading and Body Font:** DM Sans, with the system fallbacks in frontmatter. **Identifier Font:** JetBrains Mono with SF Mono and monospace fallbacks in incumbent technical identifiers; Meeting Prep source records retain DM Sans.
### Hierarchy

- **Headline:** page and brief headings; mobile brief headings reduce to (20px).
- **Section title:** brief section headings, bold within the compact text scale.
- **Item title / body:** the brief's working content, separated primarily by weight and spacing.
- **Label:** form labels and toolbar controls; fields themselves use (13px) with (1.4) line height.
- **Metadata:** secondary dates, state context and source descriptions. Existing chips use (11px), references (10.5px); these are compact supporting treatments.

The inherited body line height is (1.55), with slight negative tracking (-0.008em). There is no oversized display role in Meeting Prep.

**The Compact Hierarchy Rule.** Establish hierarchy through weight, spacing and a restrained size ramp; keep the brief in the existing DM Sans family.

## Layout

The desktop shell is a fixed-height flex layout: sidebar (220px), topbar (52px) and an independently scrolling page with (20px) padding. Meeting Prep centers within a maximum width of (1440px). Its setup form uses three columns, with focus spanning two columns and generation occupying the remaining column.

The prepared workspace places a flexible brief beside a (300px) evidence/news rail with a (16px) gap. Brief sections use (24px) horizontal insets, (20px) vertical spacing and subtle dividers. Card content commonly uses (14px 16px); card headers use (12px 16px). The recurring spacing steps are listed in frontmatter.

- At viewport widths of at least (1500px), brief sections become two columns.
- At (1100px) and below, the evidence rail moves below the brief into two columns.
- At (768px) and below, the sidebar hides and a labeled page selector appears in the topbar. Page padding becomes (14px); heading and evidence stack. Client, focus and generation span the form width while date/time share a row. Toolbar actions wrap and flex; brief insets become (18px).

Printing has a separate A4 layout with (10mm) margins: shell and editing controls hide, brief sections use two columns, and review status plus a source index appear. Direct PDF download is a separate server-rendered export of the current draft.

### Calendar extension

Calendar uses the existing shell as its default entry, with a compact heading, next-client-meeting strip and wrapping week toolbar above a bordered, internally scrolling work-week frame. The synthetic schedule contains thirty-five events across adjacent weeks, including twelve client meetings, alongside internal meetings, focus time and personal commitments. At desktop widths, weekday headings and the time grid align to a (58px) time gutter plus five equal Monday–Friday columns. Ten hourly rows run from (8 AM) through (5 PM), with a (96px) hour height; appointment position and height follow New York start time and duration. The current day uses a quiet blue-tinted column and blue date circle; a fine red line marks the current demo time. Initial scrolling places the demo time or the returned meeting roughly two hours below the top of the grid.

At (768px) and below, retain all five weekday selectors above a single selected day and a (48px) time gutter. A blue inset underline distinguishes the selected day from the current-day circle. Meetings gain wider horizontal insets and slightly larger text. The next-meeting strip wraps its client, state and action, and the category legend retains **All meeting briefs** on its own row. At (1100px) and below the inline automatic-prep status hides; on mobile the work-week label also hides while navigation and meeting access remain available.

### Meeting Prep workspace extension

The scheduled-meeting workspace centers within a maximum width of (1600px). A sticky dated meeting list (268px) sits beside a flexible detail area with a (24px) gap. At (1100px) and below the list narrows to (230px) and the gap becomes (16px). The selected brief uses one column of document sections; evidence and news sit in two columns below it, stack at (1100px) and below, and move into a (280px) rail at widths of at least (1700px).

At (768px) and below, show the meeting list or the selected detail as separate views. Selecting a row opens the detail; **All meetings** returns to the list. The list loses its sticky positioning and internal height cap, and evidence/news stack. Keep the client heading, meeting context, At a glance summary and wrapping review/export controls readable in this single-column flow. Printing hides the workspace heading, meeting list and mobile back control before applying the existing brief print layout.

## Elevation & Depth

Resting cards, the brief and evidence panels are flat. White surfaces, quiet gray interiors and one-pixel borders provide depth. Meeting Prep focus uses a blue (2px) outline offset by (3px), including the selected evidence heading.
### Shadow Vocabulary

- **Client-card hover:** `0 0 0 1px var(--accent), 0 4px 16px rgba(53,99,233,0.08)`; exclusive to the incumbent interactive client-card treatment.

**The Bordered Surface Rule.** Separate resting surfaces with neutral fills and fine borders; reserve the incumbent hover shadow for interactive client cards.

### Calendar overlays

Calendar appointments and the calendar frame remain flat and bordered. Two scoped overlays extend the resting-surface rule: the white Demo settings popover uses `0 8px 24px #1a1f2e14`; the centered event-details and meeting-ready dialogs use `0 18px 60px #18213726` over a translucent neutral backdrop (`rgba(26,31,46,.25)`). These shadows identify temporary layers rather than reusable resting-card elevation. The dialog enters with a short vertical movement (8px over 0.18s, ease-out) only when reduced motion is not requested. Calendar controls retain the blue (2px) focus outline with (3px) offset.

## Shapes

Use gently rounded rectangles: small controls and chips use `sm`, navigation uses `nav`, and cards use `md`. The larger `lg` token belongs to the incumbent system, not a new Meeting Prep card shape. References are smaller rounded text buttons. Cards clip their content; brief sections remain open document rows divided by fine rules.

## Components
### Buttons

Meeting Prep primary and secondary buttons share compact padding, a (38px) minimum height and medium-weight (12px) text. Primary is blue on white text and darkens to `#2c52c5` on hover. Secondary uses a white surface, neutral border and secondary ink; hover uses the hover surface. Disabled actions use (0.5) opacity and a disabled cursor. Use the visible focus outline described above.
### Chips and source references

Status chips pair semantic soft fills with explicit state text. Draft and Reviewed use amber and green; the synthetic-data label remains visible. Reference buttons use a blue soft fill and strengthen to `accent-medium` on hover or selection. Selecting a reference or news item opens its original record, moves focus to the evidence heading and scrolls it into view. The original-record list also shows selection through `aria-pressed` styling.
### Cards and inputs

Cards use a white fill, subtle border and standard card radius, with header/content separation. Fields use a neutral stroke, small radius and the same white surface. Labels sit above controls with a (6px) gap. Editable brief fields use the same treatment; textareas resize vertically. Error messages combine red text, soft red fill and explicit alert copy.
### Navigation and entry

Retain the incumbent sidebar structure, SVG icons and blue soft active state. Navigation text is (13px), medium weight, with a short (0.12s ease) state transition. Meeting Prep sits in the Main group and is also reached from the client-detail **Generate Meeting Brief** action, which carries the selected client into the form. Mobile uses the topbar page selector.

Copilot adds an inline meeting confirmation form using the existing field and button vocabulary. Client and focus span the form width; New York date and time share a row. Missing or ambiguous details stay empty for advisor confirmation. The generated summary provides **Open Meeting Brief**, which opens the same brief object in Meeting Prep without regeneration. Conversation history survives navigation during the current page session, and the latest local edits/review state are restored by brief ID. New chat responses scroll into view and are announced in the conversation log.
### Meeting brief and evidence

Keep six named sections: Client Overview, Recent Changes & Requests, Portfolio Highlights, Discussion Priorities, Open Actions, and Items to Confirm. Title, date/time, focus, data date and synthetic attribution form the brief header. Evidence and Relevant News share the same card grammar in the adjacent rail.

The toolbar keeps Edit draft, Mark as reviewed, Print and Download PDF together. Editing resets review status and increments the revision; local browser storage retains the latest draft and review state. Changed meeting inputs display a stale-draft notice and block review/export until generation. Editing or empty required brief fields also blocks review/export. PDF export remains available for an otherwise valid unreviewed draft and includes its draft status. Keep these states explicit rather than silently implying approval.

### Calendar events and preparation entry

The calendar is first in navigation and the initial page. Timed event containers use compact rounded corners (5px): client meetings have a pale blue fill and fine blue border, internal meetings use quiet violet, and focus/personal commitments use neutral fills. Pair category color with the legend and explicit event-details text. The next upcoming client meeting uses solid action blue with white text. Its client, topic, date/time, preparation state and **View meeting prep** action also appear in the next-meeting strip above the grid.

Each event has a details button; client events also have a separate preparation action. Client events show client name, time range and, when space permits, topic; short events use a compact treatment. The preparation action reflects **Brief ready**, **Reviewed**, **Preparing brief** or **Needs attention**, with a check for ready/reviewed states. Hover slightly darkens the container and strengthens its border. Keep event-specific accessible names and visible focus treatment.

Event details use the scoped native modal treatment and show title, client when applicable, and a divided **Type / When / Where / Who** fact list, followed by the description. Client events expose preparation status and **View meeting prep**; internal, focus and personal events explicitly say that no client brief is needed.

### Meeting list, selected brief and review state

The Meeting Prep navigation item and **All meeting briefs** open the preparation workspace. The dated **Your meetings** list includes only client meetings, with client/topic search, **Upcoming / This week** range controls, explicit preparation states and a blue-soft selected row. Empty search results provide **Clear search**. **Prepare another meeting** remains a secondary entry to the manual setup form; existing client-detail and Copilot entry points retain their form/brief behavior.

Calendar preparation actions open their selected meeting directly, including future and past client meetings. Scheduled meetings selected from the list show client, topic, New York date/time and focus, explain the 24-hour automatic-preparation policy and offer **Prepare early**; past meetings offer **Prepare brief**. When automatic preparation is paused, the workspace says so, keeps existing briefs available and qualifies scheduled preparation with **when automatic prep resumes**. Pending preparation keeps client and meeting context visible; failures provide **Retry preparation**.

**Prepare another meeting** opens a fresh form inside the detail pane, preserving the dated meeting list, search and filters. Cancel restores the previous meeting; switching between existing meetings and the form retains entered values. Mobile keeps the same list-to-detail model with **All meetings**. Manual preparation inherits the calendar mode and next demo date, and does not load an unrelated cached brief.

The selected brief leads with the client name as the primary heading, a Draft or Reviewed badge, the appointment topic and New York date/time, and **Back to calendar**. **At a glance** repeats the retained brief's focus and up to three discussion-priority titles, with **Read the full brief** linking to the existing six-section document. Keep edit/check/review/print/PDF actions together below this summary. Reopening a retained brief restores local edits and review state by brief ID. Review and subsequent edits update the selected context, meeting-list state and ready-for-review count together; edits clear review. Readiness remains distinct from advisor review. Returning to Calendar selects the opened meeting's day on mobile.

### Meeting-ready notice and presenter controls

Use one centered native modal dialog for a ready notice: white surface, rounded corners (12px), width (460px), and a viewport inset of at least (16px) on each side. Padding reduces from (30px) to (25px) on mobile. A document icon, client-specific heading and divided appointment summary lead to **Later** and the blue **View meeting prep** action. Native modal behavior contains keyboard focus; Escape, the close button and Later dismiss and acknowledge the notice. Opening preparation acknowledges it as well. Show at most one automatic ready notice per page visit; other ready items remain discoverable. A topbar button with an unread count provides access to outstanding notices; mobile retains the icon and count.

Keep simulation, mode selection, advance/reset and replay controls inside the collapsed **Demo settings** disclosure. Its white bordered popover uses the scoped overlay elevation above. Default preparation is **Offline demo · No LLM**; **AI Agent · Gemini** is an explicit selection. The calendar remains labeled as a demo, and readiness indicates an available retained brief rather than advisor review.

## Do's and Don'ts
### Do:

- **Do** preserve the current sidebar, topbar, DM Sans family and compact dashboard density.
- **Do** keep source references next to the claims they support and show the selected original record in the evidence area.
- **Do** keep draft/review text, advisor-edit attribution, synthetic-data labels and export state visible.
- **Do** let action groups wrap and stack the brief and evidence on narrower screens.
### Don't:

- **Don't** introduce a new display face, decorative hero treatment or replacement visual concept for this extension.
- **Don't** apply client-card hover elevation to every resting card.
- **Don't** indicate review status or errors through color alone.
