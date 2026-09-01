# Notice Hub — Desktop Design Specification

## 1. Purpose

This document defines the implementation rules for the final Notice Hub desktop UI.

The frontend implementation must reproduce the supplied final Figma design as closely as practical while preserving the existing application behavior.

This is an implementation specification, not a request to redesign the UI.

---

## 2. Design Reference Priority

Use the supplied design references in the following strict priority order:

1. desktop-final.png
   - Final visual source of truth.
   - Highest priority for final rendered appearance.

2. desktop-final.svg
   - Geometry, dimensions, colors, borders, radii and icon-shape reference.
   - Use it to inspect precise design measurements.

3. design-spec.md
   - Defines semantic and implementation constraints that may not be obvious from the rendered design.

4. concept-reference.jpg
   - Original visual inspiration only.
   - Use only for subtle design-language context.
   - Do NOT copy layout differences from this image over the final design.

5. Existing frontend
   - Preserve behavior, routing, state, API integration and tests.
   - Existing visual styling is not authoritative when it conflicts with the final design.

If references conflict:

desktop-final.png and desktop-final.svg are authoritative.

---

## 3. Critical Implementation Rule

Do NOT implement the design by embedding desktop-final.svg as one large SVG.

Do NOT use desktop-final.png as the actual application UI.

The design must be rebuilt using real frontend components:

- React components
- semantic HTML
- CSS
- reusable icons
- reusable design tokens
- existing application state and data

The exported PNG and SVG are design references only.

---

## 4. Target Desktop Canvas

Final Figma frame:

- Width: 1440px
- Height: 900px

Primary visual QA viewport:

- 1440 × 900

The implementation should first reproduce the design accurately at this viewport.

Responsive behavior should be evaluated only after the desktop layout is visually correct.

---

## 5. App Window

Final design geometry:

- Outer canvas: 1440 × 900
- App frame:
  - x: approximately 12px
  - y: approximately 6px
  - width: approximately 1428px
  - height: approximately 888px
  - radius: approximately 10px

Approximate colors:

- Outer background: #070B11
- Main app surface: #0A0F17
- Outer frame border: subtle blue-gray, approximately #273443 at low opacity

Do NOT add macOS red/yellow/green traffic-light window controls.

Do NOT add fake operating-system window chrome.

---

## 6. Main Three-Pane Layout

The final desktop design contains three primary application regions:

1. Sidebar
2. Notice List
3. Notice Detail

The current final proportions must be preserved.

### Sidebar

Approximate geometry:

- x: 12px
- width: 282px
- height: 888px

Approximate surface:

- #0C121B

Do not substantially change the Sidebar width.

### Notice List

Approximate geometry:

- x: 294px
- width: 574px

Approximate surface:

- #0F1721

This pane contains:

- search/header region above
- list filter row
- notice rows

### Notice Detail

Approximate geometry:

- x: 868px
- width: 572px

Approximate surface:

- #0D141D

Approximate vertical pane divider:

- x: 868px

The Notice List and Notice Detail panes should remain almost equal in width.

Do NOT recreate the earlier layout where the Detail pane was substantially wider than the Notice List.

---

## 7. Global Header

Approximate geometry:

- x: 294px
- y: 6px
- width: 1146px
- height: 54px

Approximate surface:

- #0E151F

Bottom divider:

- subtle
- low contrast
- approximately #1C2734

The Global Header and the Detail Toolbar are separate UI layers.

Do NOT merge them.

The Global Header contains:

- search
- notification bell
- user/avatar area

The Detail Toolbar belongs only to the Detail pane.

---

## 8. Search Field

Approximate geometry:

- x: 312px
- y: 16px
- width: 438px
- height: 34px
- radius: 7px

Approximate surface:

- #131D29

Border:

- extremely subtle dark blue-gray

Contains:

- search icon
- placeholder text
- keyboard shortcut hint

The search field must remain visually quiet and compact.

It is a utility control, not a visual focal point.

---

## 9. Sidebar Branding

Top-left branding contains:

- Notice Hub app icon
- Notice Hub
- 吉大通知助手

Notice Hub is primary.

吉大通知助手 is secondary and lower contrast.

The app icon should remain:

- compact rounded square
- indigo / blue-violet identity
- white N mark
- subtle internal visual depth

Do not turn it into a real university logo.

Do not use strong glow.

---

## 10. Sidebar Navigation

Primary navigation contains:

- 收件箱
- 重要
- 即将截止
- 来源
- 设置

Use a consistent outline icon system.

Approximate selected item geometry:

- x: 30px
- width: 246px
- height: 36px
- radius: 7px

Selected Inbox surface:

- approximately #141E31

Selected border:

- subtle indigo-blue
- low opacity

The selected state must be clearly visible but restrained.

Do NOT turn it into a bright purple button.

---

## 11. Sidebar Count Badges

Active Inbox count badge:

- approximately 26 × 18px
- compact pill
- indigo accent

Other count badges:

- approximately 22 × 18px
- muted
- secondary hierarchy

Badges must not become large notification chips.

---

## 12. Sidebar Quick Views

Quick Views appear below the divider.

Items:

- 本周更新
- 未读
- 已收藏

The Quick Views heading remains muted.

The plus action remains subtle.

Rows should remain compact.

Numbers should align consistently on the right.

---

## 13. Today Progress Card

Approximate geometry:

- x: 30px
- y: 778px
- width: 246px
- height: 98px
- radius: 9px

Approximate surface:

- #121C28

Border:

- subtle blue-gray

Contains:

- 今日已处理
- 12 / 28
- 43% circular progress
- helper text

The progress card must remain a lightweight Sidebar status component.

Do not turn it into a large dashboard widget.

12 / 28 is the main value.

43% should remain clearly readable inside the progress ring.

---

## 14. Notice List Header

The Notice List header begins around y = 60px.

Approximate height:

- 48px

Contains:

- 全部 18
- 未读 18
- 已读
- 按截止时间 ↑
- one list/view control

Do not add unnecessary or duplicate view controls.

The active 全部 18 state should remain compact and subtly indigo-selected.

---

## 15. Notice Row Geometry

Approximate notice content area:

- x: 306px
- width: approximately 550px

Standard rows:

- approximately 76px high

Selected row:

- x: approximately 306px
- width: approximately 550px
- height: approximately 76px
- radius: approximately 7px

Selected surface:

- approximately #151D32

Selected border:

- subtle indigo
- approximately #6866C1 at low opacity

Selected state must remain visible but restrained.

No glow.

No strong shadow.

No neon border.

---

## 16. Notice Row Information Hierarchy

Each row should visually communicate:

1. Source and timestamp
2. Notice title
3. Tag, deadline and bookmark

Notice Title must be the strongest element in the row.

Recommended visual hierarchy:

Notice title:
- medium / semibold
- high-contrast secondary-primary text

Source:
- secondary

Timestamp:
- muted

Tags:
- small but readable

Do not make notice titles heavy bold.

---

## 17. Notice Source Identity Icons

Do NOT use placeholder source letters such as:

- J
- S
- C
- R

Preserve the semantic source-icon system.

### JLU OA

- blue
- university / institution building identity

### JLU 教务处

- cyan / teal
- academic institution identity

### SEU 教务

- green
- academic / university identity
- must not primarily resemble a security shield

### Campus Site

- blue-violet
- web / portal / globe identity

### RSS · 学术前沿

- green / teal
- real RSS wave symbol

All source icon containers must have consistent:

- width
- height
- radius
- optical weight
- foreground scale

Visual weight should be normalized across all sources.

---

## 18. Unread State

Unread notices use a small blue status dot.

The dot must:

- remain clearly visible
- remain secondary
- align correctly with the title
- use no glow

Read status uses a muted gray dot.

---

## 19. Notice Bookmark

Notice rows use a bookmark outline icon.

Do NOT replace the Notice List bookmark with a star.

This distinction is intentional:

- Detail Toolbar Favorite uses a star
- Notice Row quick action uses a bookmark

---

## 20. Notice Row Separators

Normal row separators must remain extremely subtle.

The Notice List should NOT resemble:

- a spreadsheet
- a data table
- an admin table

Use:

- spacing
- surface hierarchy
- subtle separation

as the primary means of distinguishing rows.

The selected row provides the strongest row boundary.

---

## 21. Deadline Pills

Deadline states include:

- 今天截止
- 2天后截止
- 3天后截止
- 5天后截止
- 已结束

Use muted semantic colors.

Approximate semantics:

今天截止:
- dark muted red

2天后截止 / 3天后截止:
- muted amber / brown

5天后截止:
- muted blue-gray

已结束:
- neutral dark gray

No glow.

No highly saturated warning colors.

---

## 22. Detail Toolbar

The Detail Toolbar appears at the top of the Detail pane.

Approximate height:

- 42px

Actions:

1. 收藏
2. 标记已读
3. 打开原文
4. …

Do NOT add the word 更多 after the ellipsis.

Toolbar items must remain lightweight actions.

Do not use filled button backgrounds.

---

## 23. Detail Toolbar Color Rules

This is an important visual requirement.

### 收藏

Icon:

- outline star
- blue-violet / indigo accent

Text:

- neutral soft white / light gray

Do NOT color the entire label purple.

### 标记已读

Icon:

- outline circle-check
- same blue-violet / indigo accent family

Text:

- neutral soft white / light gray

### 打开原文

Icon:

- neutral soft white / light gray

Text:

- neutral soft white / light gray

### More

Display only:

…

Color:

- muted gray

No glow.

No filled toolbar buttons.

---

## 24. Detail Toolbar Typography

Toolbar text should use approximately medium weight.

Do not make:

- 收藏
- 标记已读
- 打开原文

look heavy or bold.

Toolbar icons may carry slightly more visual emphasis than their labels.

Action gaps must remain compact but clearly separated.

---

## 25. Detail Content Grid

Approximate Detail content left edge:

- x: 898px

This corresponds to approximately:

- 30px left padding inside the Detail pane

Approximate primary right content edge:

- x: 1410px

This corresponds to approximately:

- 30px right padding

Maintain this shared content grid for:

- title
- metadata
- tags
- divider
- body
- attachments
- CTA

---

## 26. Detail Title

Title:

关于暑期值班安排的通知

This is the strongest typography in the Detail pane.

Visual intent:

- approximately 23–25px optical size
- semibold
- high-contrast soft white
- compact line height

Do NOT turn it into an oversized landing-page hero title.

Do not increase it beyond the final design.

---

## 27. Detail Metadata

Required structure:

[institution icon] JLU OA    发布时间：2025-06-03 09:32

with the deadline aligned to the right:

今天截止 23:59

Do NOT move the deadline onto a separate row.

The deadline pill should align optically with the metadata row.

JLU OA should be slightly brighter than the publication timestamp.

---

## 28. Detail Institution Icon

The icon immediately before JLU OA in the Detail metadata must be:

- monochrome
- university / institutional building outline

It must NOT be:

- a home icon
- a location icon
- a J letter
- the colored List source badge

The metadata icon and the List source identity icon intentionally serve different visual roles.

---

## 29. Detail Deadline

Approximate geometry:

- width: approximately 96px
- height: approximately 24px
- radius: approximately 6px

Use a muted dark red.

It must be visible but not compete with the Detail title.

Keep it aligned to the shared Detail right edge.

---

## 30. Detail Tags

Current visual examples:

- 校务通知
- 值班安排
- 重要

Approximate height:

- 25px

Approximate widths:

- 校务通知: 65px
- 值班安排: 65px
- 重要: 45px

Semantics:

校园/校务通知:
- muted blue

值班安排:
- neutral blue-gray

重要:
- muted red

Tags are labels, not buttons.

Do not add hover/button-like visual weight to them.

---

## 31. Detail Divider

Approximate divider geometry:

- x: 898px
- width: approximately 512px

The divider must remain low contrast.

Do not use strong horizontal rules.

---

## 32. Detail Section Heading

正文摘要 is a section heading.

It should:

- be clearly distinguishable from body copy
- remain smaller than the Detail title
- use moderate weight
- maintain compact spacing

Do not make it a large heading.

---

## 33. Body Content

Body typography must be clearly more readable than metadata.

Required hierarchy:

Primary body text
>
metadata
>
muted helper text

The body must not be so gray that it requires effort to read.

Use compact but comfortable line-height.

Do not expand the Detail reader width.

---

## 34. Bullet List

The body includes:

- 值班时间
- 值班地点
- 值班要求

Use:

- small left indentation
- consistent bullet-to-text spacing
- consistent vertical item gap

Do not use oversized bullets.

Do not compress bullet lines excessively.

---

## 35. Attachments

Approximate attachment row geometry:

- x: 898px
- width: 512px
- height: 46px
- radius: 7px

Two rows:

1. 暑期值班安排表.xlsx
2. 值班注意事项.pdf

Required structure:

[file type icon] filename        file size        download

Do NOT return to a two-line oversized attachment card layout.

---

## 36. Attachment File Type Icons

XLSX:

- muted green
- spreadsheet / Excel identity

PDF:

- muted red
- PDF/document identity

Use compact file-type icon containers.

The icon must remain clearly identifiable without dominating the attachment row.

---

## 37. Attachment Text Hierarchy

Filename:

- primary / secondary-high contrast

File size:

- muted

Download icon:

- outline
- right aligned
- vertically centered
- subtle

File size must not visually compete with the file name.

---

## 38. CTA

Final CTA geometry:

- x: 898px
- width: 512px
- height: 38px
- radius: 7px

Text:

打开原文链接

Approximate surface:

- deep indigo / violet-blue
- approximately #4E50B6

Do not make the CTA:

- neon
- overly bright
- oversized
- pill-shaped
- strongly glowing

Keep the external-link icon subtle.

The CTA is the primary final action in the Detail pane, but it should not dominate the entire page.

---

## 39. Core Surface Palette

Useful approximate Figma-derived colors:

Outer background:
#070B11

App surface:
#0A0F17

Sidebar:
#0C121B

Global header:
#0E151F

Notice list:
#0F1721

Detail:
#0D141D

Search:
#131D29

Selected notice:
#151D32

Attachment row:
#101A25

Progress card:
#121C28

CTA:
#4E50B6

These values may be normalized into reusable frontend design tokens.

The final rendered result must remain visually faithful to desktop-final.png.

---

## 40. Typography Color Hierarchy

Useful approximate foreground families:

Primary:
- #EBF0F7
- #E8EDF5
- #E0E6EE

Secondary:
- #BAC4D1
- #B0BAC8

Metadata:
- #96A3B4
- #8996A8

Muted:
- #7F8DA0
- #657387

Do not create dozens of almost-identical text color variables.

Build a small coherent token system while matching the final appearance.

---

## 41. Iconography

Functional icons should share:

- similar stroke weight
- similar optical size
- consistent corner style
- consistent baseline

This includes:

- Sidebar navigation icons
- Search icon
- Toolbar icons
- Bookmark
- Download
- External Link
- Bell
- View control
- Detail metadata institution icon

Source Identity icons may use colored containers.

Do not use emoji.

Do not mix arbitrary filled and outline icon styles.

---

## 42. Global Alignment Requirements

Perform a final alignment pass.

### Notice List right-side grid

The following must align consistently:

- timestamp
- deadline pill
- bookmark

Use reusable layout rules rather than manually positioning each row.

### Detail left edge

These should use the same primary content left edge:

- Detail title
- metadata
- tags
- divider
- 正文摘要
- body
- attachments heading
- attachment rows
- CTA

### Detail right edge

These should share a consistent right edge:

- deadline
- divider
- attachment rows
- CTA

### Sidebar

Ensure stable alignment between:

- navigation icon
- navigation label
- badge

and between:

- Quick View icon
- Quick View label
- Quick View number

---

## 43. Border and Divider System

Borders should remain subtle throughout the UI.

Use stronger visibility only for:

- selected notice
- active navigation item
- focus states when needed

Keep low contrast for:

- Search border
- Attachment borders
- panel dividers
- normal Notice Row separators

Do not use bright borders as decorative styling.

---

## 44. Radius System

Maintain a restrained radius hierarchy.

Approximate examples:

App frame:
- 10px

Progress card:
- 9px

Search:
- 7px

Selected notice:
- 7px

Attachment:
- 7px

CTA:
- 7px

Deadline:
- approximately 6px

Do not make every component into a large rounded pill.

---

## 45. Shadow and Glow Rules

The final design uses extremely restrained depth.

Do not introduce:

- neon glow
- strong indigo shadow
- purple ambient bloom
- floating SaaS card shadows

If shadow is needed, it must remain extremely subtle.

Selection should rely mainly on:

- surface tint
- thin border
- contrast

not glow.

---

## 46. Visual Character

The final product should feel like:

- premium desktop productivity application
- compact notification/mail client
- high information density
- dark navy
- subtle indigo
- low visual noise
- precise alignment
- restrained borders
- clear typography
- mature interface

It must NOT feel like:

- generic admin dashboard
- card-heavy SaaS interface
- cyberpunk/neon UI
- giant mobile UI stretched to desktop
- spreadsheet
- data table

---

## 47. Prohibited Visual Changes

Do NOT introduce:

- macOS red/yellow/green traffic lights
- neon glow
- strong purple shadows
- oversized cards
- large dashboard statistics
- charts
- new navigation entries
- new product features
- J/S/C/R placeholder source icons
- List star replacing bookmark
- home icon for Detail JLU OA metadata
- oversized CTA
- major three-pane layout changes
- random gradients
- new decorative widgets

---

## 48. Existing Functionality Must Be Preserved

Do not break existing application behavior.

Preserve:

- routing
- Notice selection
- read/unread behavior
- favorites
- filters
- search
- Settings
- API integration
- attachments
- original-link behavior
- responsive behavior
- local persistence where already implemented
- tests
- E2E journeys

The UI redesign must not regress product functionality.

---

## 49. Existing Frontend Architecture

Prefer adapting existing reusable frontend components.

Do not duplicate entire components solely to reproduce the design.

Prefer:

- shared design tokens
- reusable Notice Row
- reusable Tag
- reusable Deadline pill
- reusable Source Icon
- reusable Attachment Row
- reusable toolbar actions

Avoid large one-off CSS overrides that make future maintenance difficult.

---

## 50. Desktop First

Visual implementation must first be validated at:

1440 × 900

Do not compromise the Desktop reference prematurely in order to optimize mobile behavior.

Once Desktop is accurate, existing responsive behavior can be preserved or adjusted carefully.

---

## 51. Visual QA Workflow

Do not consider implementation finished after the first CSS pass.

Required workflow:

1. Inspect the current frontend architecture.
2. Inspect desktop-final.png.
3. Inspect desktop-final.svg.
4. Read this design specification.
5. Preserve current behavior and tests.
6. Implement the design using real frontend components.
7. Start the real application.
8. Render at exactly 1440 × 900.
9. Capture an implementation screenshot.
10. Compare that screenshot against desktop-final.png.
11. Identify concrete visible differences.
12. Correct those differences.
13. Capture another screenshot.
14. Compare again.
15. Continue until major visible differences are removed.

Perform at least two visual comparison passes unless the first implementation is already exceptionally close.

---

## 52. Visual QA Priority

Correct differences in this order:

1. Overall application geometry
2. Three-pane widths
3. Global Header height
4. Pane boundaries
5. Main content alignment
6. Notice Row geometry
7. Detail content width
8. Typography size
9. Typography weight
10. Spacing
11. Source Icon dimensions
12. Functional icon dimensions
13. Selected state
14. Surface colors
15. Borders
16. Tags
17. Deadline pills
18. Detail metadata
19. Attachments
20. CTA
21. Minor optical polish

Do not spend time polishing tiny icon details while large geometry differences remain.

---

## 53. Reference Conflict Rules

If desktop-final.png and concept-reference.jpg differ:

Use desktop-final.png.

If desktop-final.svg geometry and old frontend CSS differ:

Use desktop-final.svg.

If existing frontend visual styling differs from this specification:

Use this specification.

If browser rendering prevents mathematically identical appearance:

Match the visual result rather than blindly copying a numerical value.

---

## 54. Definition of Done

The Desktop implementation is visually complete only when:

- the 1440 × 900 implementation screenshot is clearly recognizable as the same design as desktop-final.png
- Sidebar geometry closely matches
- Notice List geometry closely matches
- Detail geometry closely matches
- Global Header matches
- Search matches
- Notice Row density matches
- typography hierarchy matches
- selected Notice Row matches
- Source Identity icons are correct
- List Bookmark remains a bookmark
- Detail Toolbar accent colors match
- Detail institution icon is correct
- Detail metadata layout matches
- deadline placement matches
- tags match
- body readability matches
- attachments match
- CTA matches
- Sidebar progress card matches
- no major unexplained spacing discrepancy remains
- no major unexplained color discrepancy remains
- existing product behavior remains functional
- existing frontend tests remain passing

Pixel-perfect mathematical identity is not required where browser, font, SVG or operating-system rendering naturally differs.

However, visible discrepancies must not be dismissed as “close enough” without first attempting to identify and correct their cause.