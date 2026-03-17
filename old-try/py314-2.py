
import sys
import tarfile

from compression import zstd
from pathlib import Path


def safe_create_zstd_tar(output_path: Path, path: Path, level=6):
    """安全创建 zstd tar 文件"""
    try:
        # 验证压缩等级
        if not 1 <= level <= 22:
            raise ValueError(f"压缩等级必须在 1-22 之间，当前: {level}")
        
        # tarfile 里的 zstd 不支持参数
        # options = { 
        #     zstd.CompressionParameter.compression_level : int(sys.argv[3]),
        #     zstd.CompressionParameter.nb_workers : int(sys.argv[4]), # 使用8线程压缩
        # }


        tar: tarfile.TarFile
        # with tarfile.open(output_path, 'w:zst', dereference=True, options=options) as tar:
        # with tarfile.open(name=output_path, mode='w|zst', dereference=True) as tar:
        with tarfile.open(name=output_path, mode='w|zst') as tar:
            if path.exists():
                tar.add(path)
            else:
                print(f"警告: 文件不存在 - {path}")
        
        return True
    
    except tarfile.CompressionError as e:
        print(f"压缩错误: {e}")
        return False
    # except Exception as e:
    #     print(f"未知错误: {e}")
    #     return False


def untar(input_tar: Path, output_dir: Path):

    tar: tarfile.TarFile
    with tarfile.open(input_tar, "r|zst") as tar:
        tar.extractall(output_dir)

if __name__ == "__main__":
	# safe_create_zstd_tar(Path(sys.argv[1]), Path(sys.argv[2]))
    untar(Path(sys.argv[1]), Path(sys.argv[2]))
