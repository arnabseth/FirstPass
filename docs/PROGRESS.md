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
| **M2_ALGO** | Sharpness scoring (Laplacian) & Burst clustering (pHash) | `src/core/sharpness.py`, `src/core/hashing.py`, `tests/test_algo.py` | **TODO** | Pending | - |
| **M3_UI_SHELL** | PyQt6 Main Window, QSS theme, thumbnail grid | `src/ui/main_window.py`, `src/ui/styles.py`, `src/ui/survey_view.py` | **TODO** | Pending | - |
| **M4_ASYNC** | Non-blocking QThread worker for folder analysis | `src/pipeline/scanner_worker.py`, `src/pipeline/data_models.py` | **TODO** | Pending | - |
| **M5_PURGE** | Non-destructive batch deletion to Trash/Recycle Bin | `src/core/file_ops.py`, `tests/test_file_ops.py` | **TODO** | Pending | - |
| **M6_PACKAGE** | Cross-platform build scripts (PyInstaller) | `build_windows.spec`, `build_mac.spec` | **TODO** | Pending | - |

---

### M1_CoreEngine
* **Step 1.1 — RAW Ingestion:** **COMPLETED**. Recursive case-insensitive scanning of ARW, CR2, CR3, NEF, DNG, RAF and RW2; hidden/system files and directories excluded.
* **Step 1.2 — Embedded Preview Extractor and Disk Cache:** **COMPLETED**. Embedded JPEG extraction, half-size fallback bounded to 1080p, quality-85 JPEG cache, EXIF DateTimeOriginal, cache reuse and stale/corrupt entry regeneration.
* **Validation (2026-10-02):** `pytest tests/test_extractor.py -v` — **20 passed in 1.52s**. Synthetic decoder/JPEG tests, installed rawpy parameter validation, scanner tests, and real rawpy rejection of invalid RAW data. Real-camera RAW throughput remains unmeasured.

## 4. Current State & Handoff Context
* **Active Milestone:** `M1_CORE_IO` completed; ready for `M2_ALGO`.
* **Current Action Item:** Implement sharpness scoring and burst clustering.
* **Open Technical Debt / Warnings:** rawpy does not support `fast_render`; fallback uses half-size output with LINEAR demosaicing and no automatic brightness. The requested built-in `hash(raw_path.name)` filename varies across Python processes and can collide for identical filenames in different folders.
* **Next Handoff Target:** Execute Milestone 2. Module 1 is included in the initial Git commit.
