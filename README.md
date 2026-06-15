<p align="center">
  <img src="icon.ico" width="128" height="128" alt="KAngel Piano">
</p>

<h1 align="center">♡ KAngel Piano ♡</h1>


<p align="center">
  <a href="https://github.com/healther3/piano_tool/releases/latest">
    <img src="https://img.shields.io/badge/⬇_下载最新版-KAngel_Piano.zip-FF69B4?style=for-the-badge" alt="Download">
  </a>
</p>

---

## 功能

- 解析 `.mid` 文件，自动模拟键盘按键在游戏内演奏钢琴
- 支持单曲播放 / 歌单循环播放
- 支持延音踏板、八度偏移、力度过滤
- 歌单管理（创建歌单、导入曲目、删除曲目）
- ESC 一键中断播放

## 快速开始

### 下载使用（推荐）

1. 前往 [Releases](https://github.com/healther3/piano_tool/releases/latest) 下载 `KAngel Piano.zip`
2. 解压到任意位置
3. 将你的 `.mid` 文件放入 `asset/` 文件夹
4. 双击 **`安装到桌面.bat`** → 桌面出现快捷方式图标
5. 双击桌面图标启动，选曲播放

> **无需安装 Python 或任何运行环境**，下载解压即用。

### 从源码运行

```bash
git clone https://github.com/healther3/piano_tool.git
cd piano_tool
pip install -r requirements.txt
python main.py
```

### 从源码打包 .exe

```bash
# 双击 build.bat，或手动执行：
python -m PyInstaller --onefile --windowed ^
  --add-data "index.html;." ^
  --add-data "core\loader.py;core" ^
  --add-data "core\manager.py;core" ^
  --icon=icon.ico ^
  --name "KAngel Piano" main.py
```

打包产物在 `dist/KAngel Piano.exe`。

## 界面预览

启动后呈现仿 Windows 桌面环境，包含三个可拖拽浮动窗口：

| 窗口 | 功能 |
|------|------|
| `KAngel_Piano.exe` | 播放器 — 状态显示、播放控制、参数设置 |
| `song_library.exe` | 曲库 — 浏览全部曲目 / 歌单内容、搜索、导入 |
| `playlists.exe` | 歌单管理 — 创建 / 查看歌单 |

底部任务栏可切换窗口，点击 **♡ KAngel** 一键显示所有窗口。

## 播放参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| Octave Shift | 音高偏移（12 = 升一个八度） | 0 |
| Min Velocity | 力度过滤阈值（过滤过轻的伴奏音） | 0 |
| Pedal | 启用延音踏板（映射到空格键） | 关 |
| Loop | 歌单播放完毕后循环 | 开 |

## 使用提示

- 点击播放后有 **3 秒倒计时**，请在此期间切换到游戏窗口
- 播放过程中按 **ESC** 或点击界面上的停止按钮可中断
- 通过「导入」按钮可用系统文件对话框选择 `.mid` 文件添加到曲库
- `.mid` 文件存放在 `asset/` 根目录或其子文件夹（子文件夹即歌单）

## 项目结构

```
piano_tool/
├── core/
│   ├── loader.py      # MIDI 解析 → 动作序列
│   ├── play.py        # 键盘模拟演奏引擎（CLI 用）
│   └── manager.py     # 歌单文件夹管理
├── asset/             # MIDI 文件和歌单目录
├── main.py            # 桌面应用入口（pywebview）
├── index.html         # UI 界面
├── icon.ico           # 应用图标
├── build.bat          # 打包脚本
└── requirements.txt   # Python 依赖
```

## 技术栈

- **Python** — 核心逻辑、MIDI 解析、键盘模拟
- **pywebview** — 本地桌面窗口（内嵌 WebView）
- **pydirectinput** — 游戏兼容的键盘输入模拟
- **mido** — MIDI 文件解析
- **PyInstaller** — 打包为独立 .exe
- **HTML/CSS/JS** — NEEDY GIRL OVERDOSE 风格前端 UI

## License

MIT
