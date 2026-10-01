# FirstPass — Brand Identity & Guidelines

## 1. Executive Summary
**FirstPass** is a high-speed, local-first photo culling application built for professional and documentary photographers. It automates duplicate burst filtering and edge-sharpness scoring without external API calls, cloud storage, or subscription models.

---

## 2. Brand Positioning
* **Name:** FirstPass
* **Tagline:** *Cull the noise. Keep the gold.*
* **Primary Function:** Standalone pre-Capture One / Lightroom desktop culler.
* **Core Value Pillars:**
  * **Zero Latency:** Embedded preview extraction bypasses full RAW decoding.
  * **Absolute Privacy:** 100% on-device local execution; zero telemetry or cloud reliance.
  * **Perceptual Accuracy:** Heuristic sharpness scoring and visual cluster detection tailored to burst sequences.
  * **Safety First:** Non-destructive workflows; non-selected items are safely moved to the OS Trash/Recycle Bin rather than permanently unlinked.

---

## 3. Visual Identity & Logo System

### 3.1 The Logomark
* **Symbolism:** An aperture ring intersecting a forward acceleration curve/arrow.
  * The **aperture blades** signify photography, mechanical precision, and optical sharpness.
  * The **circular sweep arrow** signifies the first-pass pass-through, swift triage, and agile workflow.
* **Usage Rules:**
  * Use the standalone monochrome symbol on dark backgrounds (`#121316` or `#1A1D24`).
  * Minimum clear space: 25% of mark width on all four sides.
  * Minimum digital display size: `24x24 px` (system tray), `48x48 px` (dock/taskbar).

### 3.2 Color Palette
| Token | Hex Value | Role | Description |
| :--- | :--- | :--- | :--- |
| `--bg-base` | `#0E1013` | Canvas | Ultra-dark slate surface |
| `--bg-panel` | `#16191E` | Panels | Container and sidebar surfaces |
| `--bg-card` | `#1F242C` | Cards / Thumbs | Image card backgrounds & borders |
| `--border-subtle` | `#2B313D` | Borders | Dividers and inactive borders |
| `--text-primary` | `#F1F3F5` | Typography | High-contrast body & labels |
| `--text-secondary` | `#8C96A5` | Typography | Metadata, camera tags, EXIF labels |
| `--accent-pick` | `#10B981` | Action / State | "Keeper" badge (Emerald Green) |
| `--accent-reject` | `#EF4444` | Action / State | "Reject" badge (Crimson Red) |
| `--accent-primary` | `#3B82F6` | Highlights | Active selection, buttons, progress |