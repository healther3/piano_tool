"""
KAngel Piano — Desktop Application
Uses pywebview to render the UI in a native window.
All Python ↔ JS communication goes through pywebview's js_api bridge.
"""

import os
import sys
import shutil
import threading
import time
import glob as globmod

import keyboard as kb
import requests as http_requests
import webview

# ---- Path resolution (works both in dev and after PyInstaller freeze) ----

if getattr(sys, "frozen", False):
    _BUNDLE_DIR = sys._MEIPASS
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    _APP_DIR = _BUNDLE_DIR

ASSET_DIR = os.path.join(_APP_DIR, "asset")
os.makedirs(ASSET_DIR, exist_ok=True)

PROXY_URL = "https://piano-tool.onrender.com"
CONFIG_PATH = os.path.join(_APP_DIR, "config.json")

sys.path.insert(0, os.path.join(_BUNDLE_DIR, "core"))
from loader import load_midi  # noqa: E402
import manager as _mgr  # noqa: E402
_mgr.ASSET_DIR = ASSET_DIR
create_playlist = _mgr.create_playlist
add_song_to_playlist = _mgr.add_song_to_playlist
delete_song = _mgr.delete_song

# ---- Playback engine (thread-safe, identical logic to original play.py) ----

_stop_event = threading.Event()
_pause_event = threading.Event()
_skip_event = threading.Event()
_play_lock = threading.Lock()
_status = {
    "playing": False,
    "current_song": "",
    "mode": "",
    "playlist_name": "",
    "song_index": 0,
    "total_songs": 0,
}
_status_lock = threading.Lock()


def _update(**kw):
    with _status_lock:
        _status.update(kw)


import json as _json

def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return {}

def _save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

_cfg = _load_config()
_hotkeys = {
    "stop": _cfg.get("stop_hotkey", "F6"),
    "pause": _cfg.get("pause_hotkey", "F7"),
    "skip": _cfg.get("skip_hotkey", "F8"),
}

def _on_global_stop():
    _pause_event.clear()
    _stop_event.set()
    _update(playing=False, current_song="")

def _on_global_pause():
    if _pause_event.is_set():
        _pause_event.clear()
    else:
        _pause_event.set()

def _on_global_skip():
    _skip_event.set()

def _register_all_hotkeys():
    try:
        kb.unhook_all_hotkeys()
    except Exception:
        pass
    _actions = {"stop": _on_global_stop, "pause": _on_global_pause, "skip": _on_global_skip}
    for key, action in _actions.items():
        hk = _hotkeys.get(key, "")
        if hk:
            try:
                kb.add_hotkey(hk, action)
            except Exception:
                pass

_register_all_hotkeys()


def _trigger_key(key_char):
    import pydirectinput
    pydirectinput.PAUSE = 0
    _SHIFT = {
        "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
        "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    }
    if key_char.isupper():
        pydirectinput.keyDown("shift")
        pydirectinput.press(key_char.lower())
        pydirectinput.keyUp("shift")
    elif key_char in _SHIFT:
        pydirectinput.keyDown("shift")
        pydirectinput.press(_SHIFT[key_char])
        pydirectinput.keyUp("shift")
    else:
        pydirectinput.press(key_char)


def _should_stop():
    return _stop_event.is_set() or _skip_event.is_set()


def _run_score(score, pedal):
    import pydirectinput
    pydirectinput.PAUSE = 0
    for atype, key, delay in score:
        while _pause_event.is_set():
            if _stop_event.is_set() or _skip_event.is_set():
                pydirectinput.keyUp("space"); pydirectinput.keyUp("shift")
                return False
            time.sleep(0.05)
        if delay > 0:
            end = time.time() + delay
            while time.time() < end:
                if _should_stop():
                    pydirectinput.keyUp("space"); pydirectinput.keyUp("shift")
                    return False
                if _pause_event.is_set():
                    remaining = end - time.time()
                    while _pause_event.is_set():
                        if _stop_event.is_set() or _skip_event.is_set():
                            pydirectinput.keyUp("space"); pydirectinput.keyUp("shift")
                            return False
                        time.sleep(0.05)
                    end = time.time() + max(0, remaining)
                time.sleep(0.005)
        if _should_stop():
            pydirectinput.keyUp("space"); pydirectinput.keyUp("shift")
            return False
        if atype == "note":
            _trigger_key(key)
        elif atype == "pedal_down" and pedal:
            pydirectinput.keyDown("space")
        elif atype == "pedal_up" and pedal:
            pydirectinput.keyUp("space")
    return True


def _wait_or_stop(seconds, skip_ok=False):
    end = time.time() + seconds
    while time.time() < end:
        if _stop_event.is_set():
            return False
        if skip_ok and _skip_event.is_set():
            return True
        time.sleep(0.05)
    return True


def _thread_single(path, pedal, octave, vel, cd):
    import pydirectinput
    try:
        score = load_midi(path, octave, vel)
        if not score:
            return
        _update(playing=True, current_song=os.path.basename(path), mode="single")
        if not _wait_or_stop(cd, skip_ok=True):
            return
        _run_score(score, pedal)
        pydirectinput.keyUp("space"); pydirectinput.keyUp("shift")
    except Exception as e:
        print(f"[play error] {e}")
    finally:
        _update(playing=False, current_song="")


def _thread_playlist(folder, pedal, octave, vel, loop, cd):
    import pydirectinput
    try:
        files = sorted(globmod.glob(os.path.join(folder, "*.mid")))
        if not files:
            return
        total = len(files)
        _update(playing=True, mode="playlist",
                playlist_name=os.path.basename(folder), total_songs=total)
        if not _wait_or_stop(cd, skip_ok=True):
            return
        while True:
            for i, fp in enumerate(files):
                if _stop_event.is_set():
                    return
                _skip_event.clear()
                name = os.path.basename(fp)
                _update(current_song=name, song_index=i + 1)
                try:
                    score = load_midi(fp, octave, vel)
                except Exception:
                    continue
                if score:
                    ok = _run_score(score, pedal)
                    pydirectinput.keyUp("space"); pydirectinput.keyUp("shift")
                    if not ok and _stop_event.is_set():
                        return
                if not _wait_or_stop(2, skip_ok=True):
                    return
            if not loop:
                break
    except Exception as e:
        print(f"[playlist error] {e}")
    finally:
        _update(playing=False, current_song="", mode="")


# ==================================================================
#  pywebview JS API — every public method is callable from JavaScript
#  as  await window.pywebview.api.method_name(args)
# ==================================================================

class PianoApi:
    _window = None

    # ---- Songs ----

    def get_songs(self):
        try:
            return [f for f in os.listdir(ASSET_DIR)
                    if f.lower().endswith(".mid")
                    and os.path.isfile(os.path.join(ASSET_DIR, f))]
        except Exception:
            return []

    # ---- Playlists ----

    def get_playlists(self):
        try:
            dirs = [d for d in os.listdir(ASSET_DIR)
                    if os.path.isdir(os.path.join(ASSET_DIR, d))]
            result = []
            for d in dirs:
                folder = os.path.join(ASSET_DIR, d)
                count = len([f for f in os.listdir(folder)
                             if f.lower().endswith(".mid")])
                result.append({"name": d, "count": count})
            return result
        except Exception:
            return []

    def create_playlist(self, name):
        if not name or not name.strip():
            return {"error": "名称不能为空"}
        ok = create_playlist(name.strip())
        return {"success": True, "name": name.strip()} if ok else {"error": "歌单已存在"}

    def get_playlist_songs(self, name):
        folder = os.path.join(ASSET_DIR, name)
        if not os.path.isdir(folder):
            return []
        return [f for f in os.listdir(folder) if f.lower().endswith(".mid")]

    def add_song_to_playlist_by_name(self, source_file, playlist):
        ok = add_song_to_playlist(os.path.join(ASSET_DIR, source_file), playlist)
        return {"success": True} if ok else {"error": "添加失败"}

    def remove_song(self, playlist, filename):
        ok = delete_song(playlist, filename)
        return {"success": True} if ok else {"error": "删除失败"}

    # ---- File import (native dialog) ----

    def import_midi(self):
        """Open native file picker → copy .mid to root asset dir"""
        if not self._window:
            return {"error": "窗口未就绪"}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("MIDI Files (*.mid;*.MID)",),
            allow_multiple=True,
        )
        if not result:
            return {"cancelled": True}
        imported = []
        for fp in result:
            fname = os.path.basename(fp)
            shutil.copy2(fp, os.path.join(ASSET_DIR, fname))
            imported.append(fname)
        return {"success": True, "files": imported}

    def import_midi_to_playlist(self, playlist):
        """Open native file picker → copy .mid into a playlist folder"""
        if not self._window:
            return {"error": "窗口未就绪"}
        target = os.path.join(ASSET_DIR, playlist)
        if not os.path.isdir(target):
            return {"error": "歌单不存在"}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("MIDI Files (*.mid;*.MID)",),
            allow_multiple=True,
        )
        if not result:
            return {"cancelled": True}
        imported = []
        for fp in result:
            fname = os.path.basename(fp)
            shutil.copy2(fp, os.path.join(target, fname))
            imported.append(fname)
        return {"success": True, "files": imported}

    # ---- Playback ----

    def play_single(self, filename, playlist, enable_pedal,
                    octave_shift, min_velocity, countdown):
        if _status["playing"]:
            return {"error": "正在播放中"}
        path = os.path.join(ASSET_DIR, playlist, filename) if playlist else \
               os.path.join(ASSET_DIR, filename)
        if not os.path.exists(path):
            return {"error": f"找不到文件: {filename}"}
        _stop_event.clear()
        _pause_event.clear()
        _skip_event.clear()
        t = threading.Thread(target=_thread_single,
                             args=(path, enable_pedal, int(octave_shift),
                                   int(min_velocity), int(countdown)),
                             daemon=True)
        t.start()
        return {"success": True}

    def play_playlist(self, playlist, enable_pedal,
                      octave_shift, min_velocity, loop_forever, countdown):
        if _status["playing"]:
            return {"error": "正在播放中"}
        folder = os.path.join(ASSET_DIR, playlist) if playlist else ASSET_DIR
        if not os.path.isdir(folder):
            return {"error": "目录不存在"}
        _stop_event.clear()
        _pause_event.clear()
        _skip_event.clear()
        t = threading.Thread(target=_thread_playlist,
                             args=(folder, enable_pedal, int(octave_shift),
                                   int(min_velocity), loop_forever,
                                   int(countdown)),
                             daemon=True)
        t.start()
        return {"success": True}

    def stop_playback(self):
        _pause_event.clear()
        _stop_event.set()
        _update(playing=False, current_song="", mode="")
        return {"success": True}

    def pause_playback(self):
        if _pause_event.is_set():
            _pause_event.clear()
            return {"success": True, "paused": False}
        else:
            _pause_event.set()
            return {"success": True, "paused": True}

    def skip_song(self):
        _skip_event.set()
        return {"success": True}

    def get_status(self):
        with _status_lock:
            st = dict(_status)
            st["paused"] = _pause_event.is_set()
            return st

    # ---- Hotkey config ----

    def get_hotkeys(self):
        return dict(_hotkeys)

    def set_hotkey(self, action, hotkey):
        hotkey = hotkey.strip()
        if not hotkey or action not in _hotkeys:
            return {"error": "无效的快捷键设置"}
        _hotkeys[action] = hotkey
        _register_all_hotkeys()
        cfg = _load_config()
        cfg[f"{action}_hotkey"] = hotkey
        _save_config(cfg)
        return {"success": True, "action": action, "hotkey": hotkey}

    # ---- MidiShow integration ----

    def midishow_health(self):
        try:
            r = http_requests.get(f"{PROXY_URL}/api/health", timeout=10)
            return r.json()
        except Exception as e:
            return {"status": "unreachable", "message": str(e)}

    def search_midishow(self, query, page=1, sort="default"):
        try:
            r = http_requests.get(
                f"{PROXY_URL}/api/search",
                params={"q": query, "page": int(page), "sort": sort},
                timeout=20,
            )
            return r.json()
        except Exception as e:
            return {"error": f"搜索失败: {e}", "results": []}

    def download_midishow(self, url, target_playlist=""):
        """Download a MIDI file via the proxy and save to asset/."""
        try:
            r = http_requests.get(
                f"{PROXY_URL}/api/download",
                params={"url": url},
                timeout=60,
                stream=True,
            )
            if r.status_code != 200:
                try:
                    err = r.json().get("error", "下载失败")
                except Exception:
                    err = f"HTTP {r.status_code}"
                return {"error": err}

            fname = "download.mid"
            xfn = r.headers.get("X-Filename")
            if xfn:
                fname = xfn
            else:
                cd = r.headers.get("Content-Disposition", "")
                if "filename=" in cd:
                    import re
                    m = re.search(r'filename="?([^";]+)', cd)
                    if m:
                        fname = m.group(1)

            fname = fname.strip()
            if not fname.lower().endswith(".mid"):
                fname += ".mid"

            if target_playlist:
                dest_dir = os.path.join(ASSET_DIR, target_playlist)
            else:
                dest_dir = ASSET_DIR
            os.makedirs(dest_dir, exist_ok=True)

            dest = os.path.join(dest_dir, fname)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

            return {"success": True, "filename": fname, "playlist": target_playlist}

        except Exception as e:
            return {"error": f"下载出错: {e}"}


# ==================================================================

def _on_loaded(window):
    """Called once the webview window is fully created."""
    api.set_window(window)


api = PianoApi()

# Allow set_window to be called externally
PianoApi.set_window = lambda self, w: setattr(self, '_window', w) or None


def main():
    html_path = os.path.join(_BUNDLE_DIR, "index.html")

    window = webview.create_window(
        "♡ KAngel Piano ♡",
        url=html_path,
        js_api=api,
        width=1100,
        height=720,
        min_size=(800, 500),
        background_color="#1a0a2e",
    )

    def on_start():
        api._window = window

    webview.start(on_start, debug=not getattr(sys, "frozen", False))


if __name__ == "__main__":
    main()
