import os
import shutil

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "asset")

def create_playlist(name: str) -> bool:
    """新建歌单（新建文件夹）"""
    path = os.path.join(ASSET_DIR, name)
    if not os.path.exists(path):
        os.makedirs(path)
        return True
    return False

def add_song_to_playlist(source_file_path: str, playlist_name: str) -> bool:
    """导入歌曲（将用户的 mid 文件复制到歌单文件夹下）"""
    target_dir = os.path.join(ASSET_DIR, playlist_name)
    if not os.path.exists(target_dir):
        return False
        
    try:
        shutil.copy(source_file_path, target_dir)
        return True
    except Exception as e:
        print(f"导入失败: {e}")
        return False

def delete_song(playlist_name: str, song_filename: str) -> bool:
    """删除歌曲"""
    target_file = os.path.join(ASSET_DIR, playlist_name, song_filename)
    if os.path.exists(target_file):
        os.remove(target_file)
        return True
    return False