# FirstPass — UI Guide & Keyboard-First Interaction System

## 1. Design Philosophy
FirstPass is built for speed. Photographers working through 1,500+ frames should not need to reach for the mouse. The interface must be completely navigable via single-key actuation.

---

## 2. Window Layout & Zones

```
+-----------------------------------------------------------------------------+
| FirstPass [v1.0]   [Folder: /Volumes/Storage/Godmother]    [Scan Folder]    |
+-----------------------------------------------------------------------------+
|  CLUSTERS (Sidebar)  |               SURVEY VIEWPORT                        |
|                      |                                                      |
|  [Group 01] (12)     |   +-----------------------+  +--------------------+  |
|  [Group 02] (34) <-- |   | [PICK] Score: 842.1   |  | [REJECT] Sc: 312.4 |  |
|  [Group 03] (08)     |   |                       |  |                    |  |
|  [Group 04] (19)     |   |                       |  |                    |  |
|                      |   |    DSC_1042.ARW       |  |    DSC_1043.ARW    |  |
|                      |   +-----------------------+  +--------------------+  |
|                      |   [1] Keep                   [0] Reject              |
+-----------------------------------------------------------------------------+
| [Selected: 112]  [Rejects: 1,288]             [Trash Rejects (Shift+Del)]   |
+-----------------------------------------------------------------------------+
```

### Zone A: Cluster Sidebar (Left)
* Lists identified scenes and burst sequences.
* Shows frame count per cluster (e.g., `Burst 04 (32 shots)`).
* Visual indicator if the cluster has been reviewed.

### Zone B: Survey Viewport (Center)
* Shows candidates in the active cluster side-by-side.
* The algorithmic winner is pinned to the left with an emerald green **PICK** ribbon.
* Sharpness score is displayed as an overlay tag.
* Spacebar opens a full-screen 100% zoom crop centered on high-contrast detail.

### Zone C: Status & Action Bar (Bottom)
* Total counts: Keepers vs. Rejects.
* Primary execution button: **"Send Rejects to Trash"** with a confirmation dialog detailing reclaimed disk space (e.g., `"Move 1,234 files (~24.6 GB) to Recycle Bin?"`).

---

## 3. Keyboard Shortcut Map

| Key | Context | Action |
| :--- | :--- | :--- |
| `Down` / `Up` | Cluster List | Move to next / previous burst cluster |
| `Left` / `Right` | Viewport | Move focus between images in current burst |
| `W` or `1` | Focused Image | Tag as **Keeper (PICK)** |
| `X` or `0` | Focused Image | Tag as **REJECT** |
| `Space` | Focused Image | Toggle 1:1 Loupe / Fullscreen view |
| `Shift + Delete` | Global | Trigger trash workflow for all rejected files |
| `Esc` | Global | Exit zoom mode / cancel active scan |

---

## 4. UI States & Edge Handling
1. **Empty State:** Clean drag-and-drop landing area with an open aperture icon and text: *"Drag a folder of RAW images here to start FirstPass"*.
2. **Scanning State:** Smooth determinate progress bar reading: *"Extracting previews... (412 / 1,420)"* followed by *"Evaluating sharpness..."*. UI remains responsive via background thread worker.
3. **Documentary Protection Alert:** If a cluster has no clear sharpness winner (e.g., low-contrast or night frames), the app flags the cluster with an amber badge: *"Low contrast scene — manual review suggested"*.