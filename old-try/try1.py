#!/usr/bin/env python3
"""
tarfile zstd 压缩/解压工具
支持 Python 3.14+ 的 tarfile 库 zstd 压缩功能
"""

import argparse
import os
import sys
import tarfile
from pathlib import Path
from fnmatch import fnmatch


def should_exclude(path: str, exclude_patterns: list[str]) -> bool:
    """检查路径是否匹配排除模式"""
    for pattern in exclude_patterns:
        if fnmatch(path, pattern) or fnmatch(os.path.basename(path), pattern):
            return True
    return False


def add_to_archive(
    tar: tarfile.TarFile,
    path: str,
    arcname: str,
    exclude_patterns: list[str],
    dereference: bool = False
) -> None:
    """递归添加文件到归档"""
    if os.path.isfile(path):
        if not should_exclude(path, exclude_patterns):
            tar.add(path, arcname=arcname, recursive=False, dereference=dereference)
    elif os.path.isdir(path):
        if not should_exclude(path, exclude_patterns):
            tar.add(path, arcname=arcname, recursive=False, dereference=dereference)
            for entry in os.scandir(path):
                new_path = os.path.join(path, entry.name)
                new_arcname = os.path.join(arcname, entry.name)
                add_to_archive(tar, new_path, new_arcname, exclude_patterns, dereference)


def compress(
    output_file: str,
    source_paths: list[str],
    exclude_patterns: list[str],
    dereference: bool = False
) -> None:
    """创建 zstd 压缩的 tar 归档"""
    with tarfile.open(output_file, 'w:zst') as tar:
        for source_path in source_paths:
            if not os.path.exists(source_path):
                print(f"警告：路径不存在 - {source_path}", file=sys.stderr)
                continue
            
            arcname = os.path.basename(source_path.rstrip(os.sep))
            add_to_archive(tar, source_path, arcname, exclude_patterns, dereference)
    
    print(f"✓ 归档创建完成：{output_file}")


def decompress(archive_file: str, dest_dir: str = '.', use_data_filter: bool = False) -> None:
    """解压 zstd 压缩的 tar 归档"""
    if not os.path.exists(archive_file):
        print(f"错误：归档文件不存在 - {archive_file}", file=sys.stderr)
        sys.exit(1)
    
    with tarfile.open(archive_file, 'r:zst') as tar:
        if use_data_filter:
            # Python 3.14+ 使用 data_filter 安全过滤器
            tar.extraction_filter = tarfile.data_filter
        tar.extractall(path=dest_dir)
    
    print(f"✓ 解压完成到：{os.path.abspath(dest_dir)}")


def list_contents(archive_file: str) -> None:
    """列出归档内容"""
    with tarfile.open(archive_file, 'r:zst') as tar:
        for member in tar.getmembers():
            print(f"{member.name} ({member.size} bytes)")


def main():
    parser = argparse.ArgumentParser(
        description='tarfile zstd 压缩/解压工具 (Python 3.14+)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s -c archive.tar.zst file1.txt file2.txt
  %(prog)s -c archive.tar.zst ./mydir --exclude "*.log" --exclude "__pycache__"
  %(prog)s -c archive.tar.zst ./mydir -h  # 跟踪符号链接
  %(prog)s -x archive.tar.zst -C /output/dir
  %(prog)s -x archive.tar.zst -H  # 安全模式解压
  %(prog)s -t archive.tar.zst
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
        help='归档文件路径 (.tar.zst)'
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
    
    # 验证文件扩展名
    if not args.archive.endswith('.tar.zst'):
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
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()