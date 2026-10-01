# FirstPass — AI Agent Implementation Playbook

This document contains step-by-step prompts designed to be handed directly to your coding agent (Codex with Sol or Antigravity with Gemini Pro). Execute them one by one.

---

## Milestone 1 Prompt: Headless Engine & Preview Extractor
```text
You are an expert Python desktop systems developer.
We are building FirstPass, a fast local RAW photo culling utility.
Please refer to docs/ARCHITECTURE.md for specifications.

Task: Implement Milestone 1 in two files:
1. `core/raw_extractor.py`:
   - Function `extract_preview(file_path: str, cache_dir: str) -> str`:
     Extract the embedded JPEG thumbnail from Sony ARW, Canon CR2/CR3, Nikon NEF, and Fuji RAF files using `rawpy`.
     Save the extracted thumbnail into `cache_dir` as a JPEG and return the path.
     Include error handling if an image has no embedded preview.
   - Function `extract_exif_time(file_path: str) -> Optional[datetime]`:
     Read EXIF `DateTimeOriginal` from the RAW file or embedded JPEG.

2. `test_extractor.py`:
   - A standalone CLI script that accepts a folder path, extracts previews for all RAW files into a `.cache/` directory, prints benchmark times per image, and exits.

Keep the code strictly modular, fully typed with Python type hints, and free of external cloud dependencies.
```

---

## Milestone 2 Prompt: Hashing & Sharpness Logic
```text
Please refer to docs/ARCHITECTURE.md.
Task: Implement Milestone 2 in the following files:

1. `core/sharpness.py`:
   - Function `calculate_sharpness(image_path: str) -> float`:
     Load the image in grayscale via OpenCV, compute `cv2.Laplacian(gray, cv2.CV_64F).var()`, and return the score.

2. `core/hashing.py`:
   - Function `cluster_bursts(image_records: List[dict], time_threshold=3.0, hash_threshold=6) -> List[List[dict]]`:
     Group images based on timestamp proximity (within `time_threshold` seconds) and perceptual hash distance (pHash distance <= `hash_threshold`).
     Within each group, mark the item with the highest sharpness score as `is_pick=True` and all others as `is_pick=False`.

3. `test_pipeline.py`:
   - A CLI script testing the end-to-end logic on a test folder and printing clustered groups with their scores and picks.
```

---

## Milestone 3 Prompt: Native PyQt6 Dark UI
```text
Please refer to docs/UI_GUIDE.md and docs/BRANDING.md.
Task: Implement Milestone 3:

1. `ui/styles.py`:
   - A modern, dark-themed QSS stylesheet matching the color tokens in docs/BRANDING.md.

2. `ui/main_window.py`:
   - Native PyQt6 main window featuring:
     - Drag-and-drop or Browse folder input.
     - Cluster sidebar listing detected burst scenes.
     - Survey viewport showing candidate thumbnails with green (Pick) and red (Reject) borders.
     - Bottom status bar showing keeper/reject counters.
     - Full keyboard navigation: Left/Right to browse, 'W' to pick, 'X' to reject.

Connect the UI to the engine using a `QThread` worker (`pipeline/scanner_worker.py`) so the UI stays 100% fluid during folder ingestion.
```

---

## Milestone 4 Prompt: Trash Purge & PyInstaller Packaging
```text
Task: Implement Milestone 4:

1. `core/file_ops.py`:
   - Function `send_rejects_to_trash(reject_paths: List[str]) -> Tuple[int, float]`:
     Safely send all rejected RAW files to the OS Recycle Bin/Trash using `send2trash`.
     Return count of trashed files and total gigabytes freed.

2. Hook the action up to `ui/main_window.py`:
   - Add a "Purge Rejects" button and `Shift+Delete` shortcut.
   - Show a native Qt confirmation dialog before trashing.

3. Provide the exact PyInstaller commands for Windows and macOS compilation.
```