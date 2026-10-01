# FirstPass — System Architecture Specification

## 1. Architecture Overview
FirstPass is structured as a modular desktop utility using **Python 3.10+** and **PyQt6 / PySide6**. It is strictly decoupled into three layers:
1. **Engine Layer (`core/`):** Pure Python modules handling file I/O, embedded JPEG extraction, perceptual hashing, and Laplacian edge calculation.
2. **State & Orchestration (`pipeline/`):** Background worker threads using `QThread` and `QObject` signals to prevent UI blocking.
3. **Interface Layer (`ui/`):** Native desktop controls, custom Qt thumbnail widgets, and survey viewers.

```
firstpass/
├── docs/
│   ├── BRANDING.md
│   ├── ARCHITECTURE.md
│   └── UI_GUIDE.md
├── core/
│   ├── __init__.py
│   ├── raw_extractor.py     # Fast embedded preview extraction (rawpy/libraw)
│   ├── hashing.py           # Perceptual hash & burst cluster logic
│   ├── sharpness.py         # Laplacian variance & edge contrast metric
│   └── file_ops.py          # Non-destructive send2trash / XMP tag writer
├── pipeline/
│   ├── __init__.py
│   ├── scanner_worker.py    # Background worker thread (QThread)
│   └── data_models.py       # ImageItem, BurstGroup, ScanResults dataclasses
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # Main shell and toolbar
│   ├── thumbnail_strip.py   # High-speed lazy-loading thumbnail scroll
│   ├── survey_view.py       # Multi-up burst comparison viewport
│   └── styles.py            # QSS dark theme stylesheet
├── main.py                  # App entry point
└── requirements.txt
```

---

## 2. Core Modules & Algorithmic Foundation

### 2.1 Fast Preview Extraction (`core/raw_extractor.py`)
* **Problem:** Decoding full sensor raw data (CR3, ARW, NEF, RAF) requires 1–3 seconds per file.
* **Solution:** Extract embedded previews. Every modern RAW format embeds a half- or full-resolution baseline JPEG within the first few megabytes.
* **Implementation:**
  * Primary: `rawpy.imread(filepath).extract_thumb()`
  * Fallback: Pure binary stream scanner or `exiftool` binding if format is proprietary/uncommon.

### 2.2 Burst Clustering (`core/hashing.py`)
Two images belong to the same burst cluster if and only if:
1. **Temporal Proximity:** $\Delta t = |t_b - t_a| \le 3.0 \text{ seconds}$ (read from EXIF `DateTimeOriginal`).
2. **Visual Proximity:** Normalized Hamming distance of their perceptual hashes satisfies:
   $$\text{HammingDistance}(\text{pHash}(A), \text{pHash}(B)) \le 6$$
* **Algorithm:** 64-bit DCT-based perceptual hash (`imagehash.phash`).

### 2.3 Sharpness Scoring (`core/sharpness.py`)
To objectively score sharpness across a burst without running a multi-gigabyte neural net:
1. Convert preview to 8-bit grayscale: $I$.
2. Compute the discrete Laplacian operator:
   $$L(x, y) = \frac{\partial^2 I}{\partial x^2} + \frac{\partial^2 I}{\partial y^2}$$
   Using a $3 \times 3$ kernel via OpenCV `cv2.Laplacian(gray, cv2.CV_64F)`.
3. Compute the **Variance of Laplacian**:
   $$\text{Score} = \text{Var}(L) = \frac{1}{N} \sum (L(x, y) - \mu_L)^2$$
4. **Burst Selection Rule:** Within each identified cluster, mark:
   $$\text{Pick} = \arg\max_{i \in \text{Cluster}} (\text{Score}_i)$$
   Mark all remaining items in the cluster as `REJECT`.

### 2.4 File Deletion & Safety (`core/file_ops.py`)
* Files are never permanently unlinked with `os.remove()`.
* All rejected batch purges use `send2trash.send2trash()`, routing to the Windows Recycle Bin or macOS Trash.

---

## 3. Dependencies
```text
PyQt6>=6.6.0
opencv-python-headless>=4.8.0
rawpy>=0.20.0
imagehash>=4.3.1
Pillow>=10.0.0
send2trash>=1.8.2
```