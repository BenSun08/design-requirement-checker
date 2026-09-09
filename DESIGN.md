---
name: Design Requirement Checker
description: Source-derived visual reference for the disposable mock prototype.
colors: {primary: "#245ba5", workspace: "#f3f5f7", surface: "#fff", ink: "#243247", muted: "#596779", border: "#d5dce4", selection: "#eaf1fb", configured: "#236142", missing: "#a12c32", struck-out: "#795119", difference: "#805312"}
typography:
  body: {fontFamily: 'Segoe UI, "Microsoft YaHei", "PingFang SC", sans-serif', fontSize: "14px"}
  table: {fontSize: "13px", lineHeight: 1.6}
  label: {fontSize: "12px"}
rounded: {control: "4px", form-field: "3px", dialog: "6px"}
spacing: {action-gap: "8px", panel-inset: "16px", workspace-inset: "24px"}
---
# Design System: Design Requirement Checker

## Overview
Extracted from `prototype/styles.css` and `prototype/index.html`; no independent visual-validation claim. The compact engineering workspace uses restrained neutral surfaces and blue actions. [UX specification](docs/ux-spec.md) owns the surface's Operate-mode direction; [product specification](docs/product-spec.md) owns product scope. This is no production-stack decision or expanded design system.
## Colors
Blue communicates action and selection; dark ink carries requirements and muted ink carries metadata. Green, red and brown supplement explicit status words. Selection does not imply engineering acceptance.
## Typography
System fonts support Chinese text without external assets. Headings use 23px/20px; summary values use 22px tabular numerals. Paragraph line height is 1.7, rising to 1.8 in comparisons. Long descriptions wrap.
## Layout
Header/navigation heights are 76px/48px. Main content has a maximum width of 1800px and padding of 18px 24px 42px. Toolbar, counts and filters precede the split workspace: `minmax(340px,40%) minmax(0,1fr)`, minimum height 520px. Rows have a 69px minimum height and 13px 16px padding; detail padding is 22px 24px. Comparisons use equal columns; management uses a dense table.
At 1100px, filters stack and the list minimum becomes 300px. At 760px, workspace and comparison columns stack, main padding becomes 12px and the result list scrolls within 330px. Management tables can scroll horizontally. Desktop remains the intended review surface.
## Elevation & Depth
Borders and tonal backgrounds separate panels. A blue inset marker identifies selection. Dialog shadow, focus outline and breakpoints are recorded in the sidecar. The stylesheet defines no animation or transition.
## Shapes
Panels, rows and tables are square; controls have small corners and buttons have a 34px minimum height. Dialogs are 580px wide, constrained to 94vw and 92vh, with scrolling.
## Components
Primary buttons use blue fill and 7px 12px padding; neutral buttons use white and a border. Hover changes background/border; disabled opacity is 0.5. Active navigation has a blue bottom border; active filters use pale blue. Keyboard focus remains visible. Comparison and context retain borders, wrapping text and distinct insertion/deletion formatting.
## Do's and Don'ts
Do preserve compact controls, dividers, explicit status words, source context and mock-data disclosure. Do keep keyboard focus visible. Don't add decorative gradients, animation or external fonts to this prototype direction; don't frame a configured result as engineering acceptance.
