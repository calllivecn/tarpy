#!/usr/bin/env python3
"""
tarfile zstd 压缩/解压工具
支持 Python 3.14+ 的 tarfile 库 zstd 压缩功能
支持标准输入/输出
"""

import argparse
import sys
import tarfile
from pathlib import Path
from fnmatch import fnmatch
from typing import BinaryIO, Optional


def should_exclude(path: Path, exclude_patterns: list[str]) -> bool:
    """检查路径是否匹配排除模式"""
    path_str = str(path)
    for pattern in exclude_patterns:
        if fnmatch(path_str, pattern) or fnmatch(path.name, pattern):
            return True
    return False


def create_dereference_filter(exclude_patterns: list[str], base_path: Path) -> callable:
    """创建 dereference 过滤器，将符号链接转换为实际文件"""
    def dereference_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        # 检查排除模式
        full_path = Path(tarinfo.name)
        if should_exclude(full_path, exclude_patterns):
            return None
        
        # 如果是符号链接，转换为普通文件
        if tarinfo.issym() or tarinfo.islnk():
            # 解析符号链接目标
            link_target = Path(tarinfo.name).parent / tarinfo.linkname if tarinfo.issym() else Path(tarinfo.linkname)
            
            # 如果是相对路径，相对于源文件位置解析
            if not link_target.is_absolute():
                # 获取原始源路径
                original_path = base_path / Path(tarinfo.name).relative_to(base_path.name) if tarinfo.name.startswith(base_path.name) else base_path / tarinfo.name
            
                # 尝试解析符号链接
                try:
                    resolved = original_path.resolve()
                    # 更新 tarinfo 为普通文件
                    tarinfo.type = tarfile.REGTYPE
                    tarinfo.linkname = ''
                    # 更新大小信息
                    stat_info = resolved.stat()
                    tarinfo.size = stat_info.st_size
                except (OSError, ValueError):
                    # 无法解析，保持原样
                    pass
        
        return tarinfo
    
    return dereference_filter


def create_exclude_filter(exclude_patterns: list[str], base_path: Path) -> callable:
    """创建排除过滤器"""
    def exclude_filter(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        # 构建完整路径用于排除检查
        full_path = base_path / Path(tarinfo.name).relative_to(base_path.name, strict=False)
        
        if should_exclude(full_path, exclude_patterns):
            return None
        return tarinfo
    
    return exclude_filter


def add_to_archive(
    tar: tarfile.TarFile,
    path: Path,
    arcname: str,
    exclude_patterns: list[str],
    dereference: bool = False
) -> None:
    """递归添加文件到归档"""
    if not path.exists():
        return
    
    # 创建过滤器
    if dereference:
        filter_func = create_dereference_filter(exclude_patterns, path)
    elif exclude_patterns:
        filter_func = create_exclude_filter(exclude_patterns, path)
    else:
        filter_func = None
    
    # 使用 tar.add() 的 filter 参数
    # Python 3.12+ 支持 filter 参数
    if filter_func:
        tar.add(str(path), arcname=arcname, recursive=True, filter=filter_func)
    else:
        tar.add(str(path), arcname=arcname, recursive=True)


def compress(
    output_file: str,
    source_paths: list[str],
    exclude_patterns: list[str],
    dereference: bool = False
) -> None:
    """创建 zstd 压缩的 tar 归档"""
    # 检查是否输出到 stdout
    if output_file == '-':
        tar_file: BinaryIO = sys.stdout.buffer
        mode = 'w|zst'  # 管道模式用于流式输出
        tar = tarfile.open(fileobj=tar_file, mode=mode)
    else:
        tar = tarfile.open(output_file, 'w:zst')
    
    try:
        for source_path_str in source_paths:
            source_path = Path(source_path_str)
            if not source_path.exists():
                print(f"警告：路径不存在 - {source_path}", file=sys.stderr)
                continue
            
            arcname = source_path.name
            add_to_archive(tar, source_path, arcname, exclude_patterns, dereference)
    finally:
        tar.close()
    
    if output_file != '-':
        print(f"✓ 归档创建完成：{output_file}")
    else:
        print("✓ 归档输出到标准输出", file=sys.stderr)


def decompress(archive_file: str, dest_dir: str = '.', use_data_filter: bool = False) -> None:
    """解压 zstd 压缩的 tar 归档"""
    # 检查是否从 stdin 读取
    if archive_file == '-':
        tar_file: BinaryIO = sys.stdin.buffer
        mode = 'r|zst'  # 管道模式用于流式输入
        tar = tarfile.open(fileobj=tar_file, mode=mode)
    else:
        archive_path = Path(archive_file)
        if not archive_path.exists():
            print(f"错误：归档文件不存在 - {archive_file}", file=sys.stderr)
            sys.exit(1)
        tar = tarfile.open(archive_file, 'r:zst')
    
    try:
        if use_data_filter:
            tar.extraction_filter = tarfile.data_filter
        tar.extractall(path=dest_dir)
    finally:
        tar.close()
    
    if archive_file != '-':
        print(f"✓ 解压完成到：{Path(dest_dir).absolute()}")
    else:
        print("✓ 从标准输入解压完成", file=sys.stderr)


def list_contents(archive_file: str) -> None:
    """列出归档内容"""
    if archive_file == '-':
        tar = tarfile.open(fileobj=sys.stdin.buffer, mode='r|zst')
    else:
        archive_path = Path(archive_file)
        if not archive_path.exists():
            print(f"错误：归档文件不存在 - {archive_file}", file=sys.stderr)
            sys.exit(1)
        tar = tarfile.open(archive_file, 'r:zst')
    
    try:
        for member in tar.getmembers():
            print(f"{member.name} ({member.size} bytes)")
    finally:
        tar.close()


def main():
    parser = argparse.ArgumentParser(
        description='tarfile zstd 压缩/解压工具 (Python 3.14+)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s -c archive.tar.zst file1.txt file2.txt
  %(prog)s -c archive.tar.zst ./mydir --exclude "*.log" --exclude "__pycache__"
  %(prog)s -c archive.tar.zst ./mydir -h  # 跟踪符号链接
  %(prog)s -c - ./mydir > archive.tar.zst  # 输出到 stdout
  %(prog)s -x archive.tar.zst -C /output/dir
  %(prog)s -x archive.tar.zst -H  # 安全模式解压
  %(prog)s -x - -C /output/dir < archive.tar.zst  # 从 stdin 解压
  %(prog)s -t archive.tar.zst
  %(prog)s -t - < archive.tar.zst  # 从 stdin 列出内容
        '''
    )
    
    # 操作模式
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '-c', '--create',
        action='store_true',
        help='创建归档'
    )
    mode_group.add_argument(
        '-x', '--extract',
        action='store_true',
        help='解压归档'
    )
    mode_group.add_argument(
        '-t', '--list',
        action='store_true',
        help='列出归档内容'
    )
    
    # 文件参数
    parser.add_argument(
        'archive',
        help='归档文件路径 (.tar.zst)，使用 "-" 表示标准输入/输出'
    )
    parser.add_argument(
        'sources',
        nargs='*',
        help='要归档的源文件或目录 (仅创建模式)'
    )
    
    # 排除功能
    parser.add_argument(
        '--exclude',
        action='append',
        default=[],
        metavar='PATTERN',
        help='排除匹配模式的文件 (可多次使用，支持通配符)'
    )
    
    # 符号链接跟踪 (创建时)
    parser.add_argument(
        '-h', '--dereference',
        action='store_true',
        help='跟踪符号链接；将它们所指向的文件归档并输出'
    )
    
    # 安全过滤器 (解压时)
    parser.add_argument(
        '-H', '--data-filter',
        action='store_true',
        help='使用 data_filter 安全模式解压 (拒绝绝对路径、设备文件、危险链接等)'
    )
    
    # 输出目录
    parser.add_argument(
        '-C', '--directory',
        default='.',
        help='解压目标目录 (默认：当前目录)'
    )
    
    args = parser.parse_args()
    
    # 验证文件扩展名（当不是 stdin/stdout 时）
    if args.archive != '-' and not args.archive.endswith('.tar.zst'):
        print("警告：建议使用 .tar.zst 扩展名", file=sys.stderr)
    
    try:
        if args.create:
            if not args.sources:
                print("错误：创建模式需要指定源文件/目录", file=sys.stderr)
                sys.exit(1)
            compress(
                args.archive,
                args.sources,
                args.exclude,
                args.dereference
            )
        elif args.extract:
            decompress(args.archive, args.directory, args.data_filter)
        elif args.list:
            list_contents(args.archive)
    except tarfile.TarError as e:
        print(f"tar 错误：{e}", file=sys.stderr)
        sys.exit(1)
    except tarfile.AbsoluteLinkError as e:
        print(f"安全错误：拒绝绝对链接 - {e}", file=sys.stderr)
        sys.exit(1)
    except tarfile.LinkOutsideDestinationError as e:
        print(f"安全错误：链接指向目标外 - {e}", file=sys.stderr)
        sys.exit(1)
    except tarfile.SpecialFileError as e:
        print(f"安全错误：拒绝设备文件 - {e}", file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        sys.exit(0)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()