import mido

# 静态常量：完整键位映射表
KEY_MAPPING = {
    # === 第 1 八度 ===
    36: '1', 37: '!', 38: '2', 39: '@', 40: '3',
    41: '4', 42: '$', 43: '5', 44: '%', 45: '6', 46: '^', 47: '7',
    # === 第 2 八度 ===
    48: '8', 49: '*', 50: '9', 51: '(', 52: '0',
    53: 'q', 54: 'Q', 55: 'w', 56: 'W', 57: 'e', 58: 'E', 59: 'r',
    # === 第 3 八度 (中央区) ===
    60: 't', 61: 'T', 62: 'y', 63: 'Y', 64: 'u',
    65: 'i', 66: 'I', 67: 'o', 68: 'O', 69: 'p', 70: 'P', 71: 'a',
    # === 第 4 八度 ===
    72: 's', 73: 'S', 74: 'd', 75: 'D', 76: 'f',
    77: 'g', 78: 'G', 79: 'h', 80: 'H', 81: 'j', 82: 'J', 83: 'k',
    # === 第 5 八度 ===
    84: 'l', 85: 'L', 86: 'z', 87: 'Z', 88: 'x',
    89: 'c', 90: 'C', 91: 'v', 92: 'V', 93: 'b', 94: 'B', 95: 'n',
    # === 最高音 ===
    96: 'm'
}

def load_midi(file_path: str, octave_shift: int = 0, min_velocity: int = 0) -> list:
    """
    内部接口：解析 MIDI 文件并转换为统一的动作序列
    :param file_path: MIDI 文件绝对路径
    :param octave_shift: 音高偏移量（按半音计算，12 表示升一个八度，-12 表示降一个八度）
    :param min_velocity: 最低力度过滤阈值（0-127），低于该力度的音符将被忽略
    :return: 动作列表 [('note'/'pedal_down'/'pedal_up', key, delay), ...]
    """
    # clip=True 自动修复/忽略非法的越界字节
    mid = mido.MidiFile(file_path, clip=True)
    score_data = []
    
    current_wait_time = 0.0
    is_first_action = True

    for msg in mid:
        current_wait_time += msg.time
        
        # 1. 处理音符事件
        if msg.type == 'note_on' and msg.velocity > 0:
            # 过滤过轻的伴奏音
            if msg.velocity < min_velocity:
                continue
                
            # 应用音高偏移
            shifted_note = msg.note + octave_shift
            key = KEY_MAPPING.get(shifted_note)
            
            if key:
                delay = 0.0 if is_first_action else current_wait_time
                score_data.append(('note', key, delay))
                current_wait_time = 0.0
                is_first_action = False
                
        # 2. 处理延音踏板事件
        elif msg.type == 'control_change' and msg.control == 64:
            delay = 0.0 if is_first_action else current_wait_time
            if msg.value >= 64:
                score_data.append(('pedal_down', 'space', delay))
            else:
                score_data.append(('pedal_up', 'space', delay))
            current_wait_time = 0.0
            is_first_action = False

    return score_data
# 测试一下能不能正常解析
if __name__ == "__main__":
    # 填入你左侧目录里的路径
    #path = "../asset/圣诞快乐劳伦斯先生.mid" 
    #path = "../asset/asset/夜之向日葵.mid"
    
    path = "../asset/asset/夢の歩みを見上げて.mid"

    try:
        data = load_midi(path)
        print(f"解析成功！共提取了 {len(data)} 个音符动作。")
        print("前 10 个动作预览:", data[:10])
    except Exception as e:
        print(f"解析失败: {e}")