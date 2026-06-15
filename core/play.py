import pydirectinput
import time
import os
import keyboard
import glob
from loader import load_midi

# 初始化配置
pydirectinput.PAUSE = 0

_SHIFT_SYMBOLS = {
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
    '^': '6', '&': '7', '*': '8', '(': '9', ')': '0'
}

def _trigger_key(key_char):
    """内部私有函数：执行底层物理按键"""
    if key_char.isupper():
        pydirectinput.keyDown('shift')
        pydirectinput.press(key_char.lower())
        pydirectinput.keyUp('shift')
    elif key_char in _SHIFT_SYMBOLS:
        pydirectinput.keyDown('shift')
        pydirectinput.press(_SHIFT_SYMBOLS[key_char])
        pydirectinput.keyUp('shift')
    else:
        pydirectinput.press(key_char)

def _safe_sleep(duration):
    """内部私有函数：可随时被 ESC 打断的毫秒级休眠"""
    start_time = time.time()
    while time.time() - start_time < duration:
        if keyboard.is_pressed('esc'):
            return False
        time.sleep(0.01)
    return True

def _execute_score(score_data: list, enable_pedal: bool) -> bool:
    """内部私有函数：遍历并执行动作序列"""
    for action_type, key, delay_before_press in score_data:
        if delay_before_press > 0:
            if not _safe_sleep(delay_before_press):
                return False
        
        if keyboard.is_pressed('esc'):
            return False
        
        if action_type == 'note':
            _trigger_key(key)
        elif action_type == 'pedal_down' and enable_pedal:
            pydirectinput.keyDown('space')
        elif action_type == 'pedal_up' and enable_pedal:
            pydirectinput.keyUp('space')
            
    return True


# =====================================================================
#                          对外标准公共接口
# =====================================================================

def play_single(file_path: str, enable_pedal: bool = False, octave_shift: int = 0, min_velocity: int = 0) -> bool:
    """
    【公共接口 1】播放单个 MIDI 文件
    :param file_path: MIDI 文件的绝对路径
    :param enable_pedal: 是否启用延音踏板
    :param octave_shift: 音高偏移量（按半音计算，12表示升一个八度）
    :param min_velocity: 最低力度过滤阈值（0-127）
    :return: True 表示顺利播放完毕，False 表示被用户中途按 ESC 中断或解析失败
    """
    if not os.path.exists(file_path):
        print(f"错误：找不到文件 {file_path}")
        return False

    try:
        score_data = load_midi(file_path, octave_shift, min_velocity)
    except Exception as e:
        print(f"解析文件失败: {e}")
        return False

    if not score_data:
        return True

    print(f"准备播放单曲: {os.path.basename(file_path)}，请在 3 秒内切回游戏窗口...")
    if not _safe_sleep(3):
        return False

    print("开始演奏...")
    success = _execute_score(score_data, enable_pedal)
    
    # 状态清理兜底
    pydirectinput.keyUp('space')
    pydirectinput.keyUp('shift')
    return success


def play_playlist(folder_path: str, enable_pedal: bool = False, octave_shift: int = 0, min_velocity: int = 0, loop_forever: bool = True):
    """
    【公共接口 2】循环播放指定目录下的所有 MIDI 文件
    :param folder_path: 包含 .mid 文件的文件夹绝对路径
    :param enable_pedal: 是否启用延音踏板
    :param octave_shift: 音高偏移量
    :param min_velocity: 最低力度过滤阈值
    :param loop_forever: 是否在歌单结束后回到第一首无限循环
    """
    search_pattern = os.path.join(folder_path, "*.mid")
    midi_files = glob.glob(search_pattern)

    if not midi_files:
        print(f"错误：目录 {folder_path} 下未找到任何 .mid 文件。")
        return

    print(f"歌单加载成功，共 {len(midi_files)} 首曲子。请在 3 秒内切回游戏...")
    if not _safe_sleep(3):
        return

    while True:
        for file_path in midi_files:
            song_name = os.path.basename(file_path)
            print(f"\n▶️ 正在播放: {song_name}")

            try:
                score_data = load_midi(file_path, octave_shift, min_velocity)
            except Exception as e:
                print(f"⚠️ 解析 {song_name} 失败，自动跳过。原因: {e}")
                continue

            if score_data:
                # 执行演奏
                finished_normally = _execute_score(score_data, enable_pedal)
                
                # 每首结束后确保状态清理
                pydirectinput.keyUp('space')
                pydirectinput.keyUp('shift')

                # 如果中途被 ESC 中断，彻底退出整个歌单循环
                if not finished_normally:
                    print("\n🛑 收到中断信号，已退出歌单播放。")
                    return

            print(f"✅ {song_name} 播放完毕。")
            
            # 曲目间留白 2 秒，同样支持 ESC 中断
            if not _safe_sleep(2):
                return

        if not loop_forever:
            print("\n歌单已播放完毕。")
            break
        print("\n🔁 准备重新循环当前歌单...")


# --- 本地开发测试桩 ---
if __name__ == "__main__":
    # 测试时可以使用这个代码块确保重构后接口功能正常
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_file = os.path.join(current_dir, "..", "asset", "夜之向日葵.mid")
    
    # 测试单曲接口（不启用踏板，音高不偏移，不进行力度过滤）
    play_single(test_file, enable_pedal=False, octave_shift=0, min_velocity=0)