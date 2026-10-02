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
| **M4_ASYNC** | Non-blocking QThread worker for folder analysis | `src/workers/cull_worker.py`, `src/ui/main_window.py`, `tests/test_file_ops_worker.py` | **COMPLETED** | Full suite: `pytest -q` — 50 passed in 1.13s | Uncommitted |
| **M5_PURGE** | Non-destructive batch deletion and desktop entry point | `src/core/file_ops.py`, `main.py`, `tests/test_file_ops_worker.py` | **COMPLETED** | Full suite: `pytest -q` — 50 passed in 1.13s | Uncommitted |
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
* **Integration Scope:** Open Folder emits `folder_selected`; Purge Rejects emits `purge_requested` with rejected PhotoItems. Modules 4 and 5 now connect background scanning and confirmed trash execution. This task's explicit colors and keyboard bindings take precedence over the older BRANDING/UI_GUIDE values.

### M4_AsyncIntegration
* **Status:** **COMPLETED**. `CullWorker(QThread)` scans directories, extracts cached previews, calculates sharpness and pHash, groups and ranks bursts, and emits progress, individual clusters, final clusters, and errors. The UI starts the worker from folder selection, displays progress, and appends ClusterRow widgets on the GUI thread.
* **Safety and Lifecycle:** Cache directories are isolated by source folder to prevent same-basename collisions. Missing capture timestamps receive isolated timestamps so unknown-time images remain singleton picks. Scanning disables purge and culling edits; Esc interrupts between pipeline operations. Closing an active scan defers window destruction until the worker stops.

### M5_FileOps
* **Status:** **COMPLETED**. Explicit rejects go through `send2trash.send2trash`; dry runs return candidates without disk changes. Preview cleanup follows successful trash moves, protects originals and previews shared by retained items, and tolerates missing cache files. Partial failures report completed paths so the UI removes only successfully trashed items.
* **Desktop Integration:** Purge uses a default-No confirmation dialog with the requested file count and updates rows and stats after acceptance. `main.py` configures Qt high-DPI rounding, creates QApplication, applies the dark theme, and shows MainWindow. `send2trash>=1.8.2` is included in requirements.
* **Final Validation (2026-10-02):** `.venv/Scripts/pytest.exe -q` across the entire project — **50 passed in 1.13s**. Includes all prior core/UI tests plus mocked trash invocation, dry-run preservation, cache safety, partial failures, actual background-thread execution, progress/result/error signals, empty scans, unknown timestamps, cache separation, folder-to-purge UI integration, and safe cancellation on window close. Tests use offscreen Qt and mocked trash operations; real OS Trash and real-camera throughput remain unmeasured. No Git commit was created.

### Scan Completion Crash Guard (2026-10-02)
* `main.py` installs an exception hook before Qt imports and enables all-thread faulthandler output using a retained duplicate stderr descriptor. Native traces remain visible during LibRaw diagnostic suppression.
* Worker signals carry only Python data and `PhotoItem` references with preview paths. GUI slots use explicit queued connections; photo widgets enforce GUI-thread construction.
* Thumbnails decode through QImageReader at bounded size and retain pixmaps no larger than 300x200. UI population uses timer batches limited to 24 cards and a 12ms work budget, including individual large clusters. Small direct populations remain synchronous for existing callers.
* Completion-only and streamed results share a deduplicated queue. Scan controls stay disabled until both the worker and UI population finish. Cancellation discards pending cards even after the worker stops; repopulation releases pixmaps and safely schedules old widget deletion. The scroll area remains widget-resizable.
* Validation: `pytest -q` — **66 passed in 6.52s**. New crash-guard tests exercise repeated 120-cluster/240-card completion, a 150-card cluster, GUI-thread delivery from an actual worker thread, event-loop responsiveness, QObject cleanup, Windows GDI handle counts, cancellation during completion rendering, and subprocess traceback output from an unhandled Qt callback. Synthetic headless coverage does not reproduce or establish the cause of the original real-camera native crash. No Git commit was created.

## 4. Current State & Handoff Context
* **Current State:** Core Application Fully Functional.
* **Active Milestone:** `M4_AsyncIntegration` and `M5_FileOps` completed.
* **Current Action Item:** Review the uncommitted implementation; launch the desktop app with `.venv/Scripts/python.exe main.py`.
* **Open Technical Debt / Warnings:** rawpy does not support `fast_render`; fallback uses half-size output with LINEAR demosaicing and no automatic brightness. Extractor cache filenames still vary across Python processes; the worker isolates source folders to prevent cross-folder collisions. Interruption is cooperative and waits for an in-flight extraction or analysis operation to finish. Real-camera throughput and actual OS Trash behavior remain unmeasured.
* **Next Handoff Target:** `M6_PACKAGE` cross-platform packaging. Changes remain uncommitted as requested.
