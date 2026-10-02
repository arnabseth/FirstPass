# FirstPass — Project Progress & State Tracker

## 1. Project Overview
* **Name:** FirstPass
* **Type:** Standalone Native Desktop RAW Image Culling Utility
* **Target Platforms:** Windows 10/11 (`.exe`), macOS 13+ (`.app`)
* **Primary Tech Stack:** Python 3.10+, PyQt6, rawpy (LibRaw), OpenCV, imagehash, send2trash

---

## 2. Environment & Tooling State
* **Python Target:** `>=3.10`
* **Virtual Environment:** Recommended `.venv`
* **Test Runner:** `pytest`
* **Core Dependencies:**
  * `PyQt6>=6.6.0` (Native GUI framework)
  * `opencv-python-headless>=4.8.0` (Variance of Laplacian edge analysis)
  * `rawpy>=0.19.0` (Embedded JPEG thumbnail extraction)
  * `imagehash>=4.3.1` (DCT perceptual hashing for burst clustering)
  * `Pillow>=10.0.0` (Image I/O for hashing)
  * `send2trash>=1.8.2` (Cross-platform non-destructive file disposal)
  * `pytest>=8.0.0` (Unit and integration testing)

---

## 3. Module Status Table

| Module ID | Module Description | Target Files | Status | Test / Validation Result | Commit Reference |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **M0_BOOTSTRAP** | Repo structure, docs, dependencies, gitignore | `requirements.txt`, `.gitignore`, `docs/*` | **COMPLETED** | Tree & environment verified | Pending Module 1 |
| **M1_CORE_IO** | RAW ingestion, embedded JPEG preview extractor, EXIF reader & disk cache | `src/core/scanner.py`, `src/core/extractor.py`, `tests/test_extractor.py` | **COMPLETED** | `pytest tests/test_extractor.py -v`: 20 passed | Initial Module 1 commit |
| **M2_ALGO** | Sharpness scoring (Laplacian) & Burst clustering (pHash) | `src/core/analyzer.py`, `src/core/clusterer.py`, `tests/test_analyzer_clusterer.py` | **COMPLETED** | `pytest tests/test_analyzer_clusterer.py -v`: 11 passed | Uncommitted |
| **M3_UI_SHELL** | PyQt6 Main Window, QSS theme, thumbnail grid | `src/ui/main_window.py`, `src/ui/theme.py`, `src/ui/components.py`, `tests/test_ui_components.py` | **COMPLETED** | `pytest tests/test_ui_components.py -v`: 7 passed | Uncommitted |
| **M4_ASYNC** | Non-blocking QThread worker for folder analysis | `src/pipeline/scanner_worker.py`, `src/pipeline/data_models.py` | **TODO** | Pending | - |
| **M5_PURGE** | Non-destructive batch deletion to Trash/Recycle Bin | `src/core/file_ops.py`, `tests/test_file_ops.py` | **TODO** | Pending | - |
| **M6_PACKAGE** | Cross-platform build scripts (PyInstaller) | `build_windows.spec`, `build_mac.spec` | **TODO** | Pending | - |

---

### M1_CoreEngine
* **Step 1.1 — RAW Ingestion:** **COMPLETED**. Recursive case-insensitive scanning of ARW, CR2, CR3, NEF, DNG, RAF and RW2; hidden/system files and directories excluded.
* **Step 1.2 — Embedded Preview Extractor and Disk Cache:** **COMPLETED**. Embedded JPEG extraction, half-size fallback bounded to 1080p, quality-85 JPEG cache, EXIF DateTimeOriginal, cache reuse and stale/corrupt entry regeneration.
* **Validation (2026-10-02):** `pytest tests/test_extractor.py -v` — **20 passed in 1.52s**. Synthetic decoder/JPEG tests, installed rawpy parameter validation, scanner tests, and real rawpy rejection of invalid RAW data. Real-camera RAW throughput remains unmeasured.

### M2_ClusteringScoring
* **Step 2.1 — Sharpness Evaluation and Perceptual Hashing:** **COMPLETED**. Grayscale Laplacian variance, zero score for unreadable previews, and DCT-based pHash with image file cleanup.
* **Step 2.2 — Burst Clustering and Ranking:** **COMPLETED**. Chronological grouping using consecutive timestamp and pHash distances, zero-based cluster IDs, sharpest-frame picks, remaining-frame rejects, and singleton picks.
* **Validation (2026-10-02):** `pytest tests/test_analyzer_clusterer.py -v` — **11 passed in 3.62s**. Synthetic sharp/blurred images, identical/inverted hashes, two-burst selection, unreadable images, empty/singleton inputs, inclusive thresholds, consecutive comparisons, custom thresholds, reranking, and tied scores.

### M3_UI_Layout
* **Step 3.1 — Native Dark Interface and Cluster Survey Layout:** **COMPLETED**. Task-specified dark QSS palette, aspect-preserving thumbnails, sharpness badges, PICK/REJECT indicators, horizontal cluster rows, scrollable survey, header controls and live counters.
* **Step 3.2 — Keyboard Culling and Selection:** **COMPLETED**. Left/Right navigation across clusters; Space picks; Delete/Backspace reject; 1/5 toggle mutually exclusive pick/reject flags. Click selection, dynamic QSS properties and border repolishing, empty-state handling and headless tests included.
* **Validation (2026-10-02):** `pytest tests/test_ui_components.py -v` — **7 passed in 0.88s**. Covers layout, thumbnail aspect ratio, resolved border colors, navigation boundaries, all culling shortcuts, mouse selection, shortcuts with button focus, repopulation, missing previews and workflow signals.
* **Integration Scope:** Open Folder emits `folder_selected`; Purge Rejects emits `purge_requested` with rejected PhotoItems. Background scanning and confirmed trash execution remain in Modules 4 and 5. This task's explicit colors and keyboard bindings take precedence over the older BRANDING/UI_GUIDE values.

## 4. Current State & Handoff Context
* **Active Milestone:** `M3_UI_SHELL` completed; ready for `M4_ASYNC`.
* **Current Action Item:** Connect background folder analysis to the UI's folder selection signal and cluster population method.
* **Open Technical Debt / Warnings:** rawpy does not support `fast_render`; fallback uses half-size output with LINEAR demosaicing and no automatic brightness. The requested built-in `hash(raw_path.name)` filename varies across Python processes and can collide for identical filenames in different folders.
* **Next Handoff Target:** Execute Milestone 4. Module 3 changes remain uncommitted as requested.
