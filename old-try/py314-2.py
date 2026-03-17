
import sys
import tarfile

from pathlib import Path


def safe_create_zstd_tar(output_path: Path, path: Path, level=6):
    """安全创建 zstd tar 文件"""
    try:
        # 验证压缩等级
        if not 1 <= level <= 22:
            raise ValueError(f"压缩等级必须在 1-22 之间，当前: {level}")
        
        tar: tarfile.TarFile
        with tarfile.open(output_path, 'w:zst', compresslevel=level) as tar:
            if path.exists():
                tar.add(path)
            else:
                print(f"警告: 文件不存在 - {path}")
        
        return True
    
    except tarfile.CompressionError as e:
        print(f"压缩错误: {e}")
        return False
    except Exception as e:
        print(f"未知错误: {e}")
        return False

if __name__ == "__main__":
	safe_create_zstd_tar(Path(sys.argv[1]), Path(sys.argv[2]))
