# CatDoll

[繁體中文](#catdoll-桌面貓) · **English**

A Windows desktop pet cat that walks along the top edge of your taskbar and occasionally curls up to sleep.

You can drag the cat with your mouse. A system tray icon lets you wake the cat, put it to sleep, or quit the app.

## Requirements

- Windows 10 / 11
- For development: Python 3.10+, PySide6, numpy
- For end users: just run the bundled `CatPet.exe` — **no Python or dependencies needed**

## Controls

| Action | What it does |
| --- | --- |
| Left-drag the cat | Pick it up and drop anywhere; on release it returns to the taskbar and keeps walking |
| Right-click the cat | Context menu (Sleep / Walk / Quit) |
| Click the tray icon (left or right) | Same menu (Wake / Sleep / Quit) |

## Run from source

```bash
pip install -r requirements.txt
python pet.py
```

The first run takes a few seconds to remove the white background from the sprite sheets and cache the result in `.cache/`. Subsequent launches start in ~0.2 s.

## Build a single .exe

```bash
build.bat
```

This produces `dist/CatPet.exe` (~35 MB). Double-click to run; the target machine does not need Python.

`build.bat` will:
1. Install / update `requirements.txt` and PyInstaller
2. Run `pyinstaller --onefile --windowed`, embedding the Python runtime, PySide6 and the three PNGs into a single executable

## Customisation

Constants near the top of `pet.py`:

| Constant | Default | Meaning |
| --- | --- | --- |
| `TARGET_HEIGHT` | `96` | Visual height of the walking cat (pixels) |
| `SLEEP_SCALE` | `0.75` | Sleeping cat size relative to the walking cat |
| `WALK_SPEED_PX` | `2` | Pixels moved per 50 ms tick |
| `STATE_MIN_MS` / `STATE_MAX_MS` | `5000` / `10000` | Random state-change interval (ms) |

## How it works

- **Background removal**: The source PNGs have an opaque white background. A flood-fill from the image edges identifies the connected white region; an extra alpha-feathering pass softens the anti-aliased grey pixels right next to that region, so the cat's body is preserved while edges fade cleanly.
- **Taskbar detection**: Uses Qt's `QScreen.availableGeometry()` so it works whether the taskbar is at the bottom, top, left, or right.
- **Per-frame window resize**: The window is resized every frame to match the current sprite's bounding box, so your wallpaper does not show through transparent padding (which would look like a dark frame around the cat).
- **Windows 11 chrome**: `DwmSetWindowAttribute` is called with `DWMWA_WINDOW_CORNER_PREFERENCE = DWMWCP_DONOTROUND` and `DWMWA_BORDER_COLOR = COLOR_NONE` to suppress Win11's default rounded corners and 1 px border on every window.

## Files

```
pet.py            Main program
catleft.png       Walk-left sprite sheet (4×2, 8 frames)
catright.png      Walk-right sprite sheet
catsleep.png      Sleep sprite sheet
requirements.txt  PySide6, numpy
build.bat         One-click .exe builder
```

## Credits

Sprite art generated with OpenAI's GPT-Image (Image 2) feature.

---

# CatDoll 桌面貓

**繁體中文** · [English](#catdoll)

一隻在 Windows 工具列上緣走來走去、偶爾蹲下睡覺的桌面寵物。

支援滑鼠拖曳；系統匣有小貓圖示，點下去可以叫醒、讓貓睡覺、或結束程式。

## 系統需求

- Windows 10 / 11
- 開發：Python 3.10+，PySide6、numpy
- 終端使用者:直接執行打包好的 `CatPet.exe`，**不需要安裝任何東西**

## 操作

| 動作 | 說明 |
| --- | --- |
| 左鍵拖曳貓 | 把貓搬到任意位置，放開後會回到工具列上緣繼續走 |
| 右鍵點貓 | 彈出選單（睡覺 / 走走 / 結束） |
| 點托盤圖示（左 / 右鍵） | 彈出選單（叫醒 / 睡覺 / 結束） |

## 從原始碼執行

```bash
pip install -r requirements.txt
python pet.py
```

第一次執行會花幾秒做去背 + 快取（存到 `.cache/`），之後啟動約 0.2 秒。

## 打包成單一 .exe

```bash
build.bat
```

完成後產出 `dist/CatPet.exe`（約 35 MB）。雙擊即可執行，目標機器不需要 Python。

`build.bat` 內部會：
1. 安裝 / 更新 `requirements.txt` 與 PyInstaller
2. 用 `pyinstaller --onefile --windowed` 把 Python runtime、PySide6、三張 PNG 全部包進 `CatPet.exe`

## 自訂

`pet.py` 最上方常數可以調：

| 常數 | 預設 | 說明 |
| --- | --- | --- |
| `TARGET_HEIGHT` | `96` | 走路貓的視覺高度（像素） |
| `SLEEP_SCALE` | `0.75` | 睡覺貓相對走路貓的縮放比 |
| `WALK_SPEED_PX` | `2` | 每個 50ms tick 移動幾像素 |
| `STATE_MIN_MS` / `STATE_MAX_MS` | `5000` / `10000` | 隨機切換狀態的間隔（毫秒） |

## 工作原理（簡述）

- **去背**：原圖白底沒有 alpha 通道。從邊緣 flood-fill 純白區得到背景遮罩，再針對緊鄰背景的灰色 anti-alias 像素做 alpha 漸變，貓本體不會被誤刪。
- **工具列偵測**：用 Qt 的 `QScreen.availableGeometry()`，自動處理工具列在底部 / 頂部 / 左右各種位置。
- **逐幀視窗大小**：每幀視窗大小貼齊當前貓的 bbox，避免桌布從透明 padding 露出來看起來像「外框」。
- **Windows 11 圓角邊框**：用 `DwmSetWindowAttribute` 設 `DWMWA_WINDOW_CORNER_PREFERENCE = DWMWCP_DONOTROUND`、`DWMWA_BORDER_COLOR = COLOR_NONE` 強制關閉 DWM 預設的圓角與 1px 邊框。

## 檔案

```
pet.py            主程式
catleft.png       向左走 sprite sheet（4×2，8 幀）
catright.png      向右走 sprite sheet
catsleep.png      睡覺 sprite sheet
requirements.txt  PySide6, numpy
build.bat         一鍵打包成 .exe
```

## 致謝

Sprite 圖檔由 OpenAI GPT-Image（Image 2）功能生成。
