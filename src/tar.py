#!/usr/bin/env python3
# coding=utf-8
# date 2019-03-20 16:43:36
# update 2022-08-18 09:39:39
# https://github.com/calllivecn


import os
import sys
import logging
import getpass
import tarfile
# import traceback
from pathlib import Path

import util
from libargparse import parse_args
from logs import logger, logger_print

from typing import (
    Optional,
)

newtars1 = (".ta", ".tza")
newtars2 = (".tar.aes",)
newtars3 = (".tar.zst.aes",)
NEWTARS = newtars1 + newtars2 + newtars3

tars1 = (".tar", ".tgz", ".tbz2", ".tbz", ".txz", ".tz")
tars2 = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")
TARFILE = tars1 + tars2


def check_suffix_newtar(f: Optional[Path]) -> bool:
    """
    从指定层级的后缀判断，是否要解密。
    """
    if f is None:
        return False

    if len(f.suffixes) >= 1 and f.suffixes[-1].lower() in newtars1:
        return True

    
    if len(f.suffixes) >= 2 and "".join(f.suffixes[-2:]).lower() in newtars2:
        return True
    

    if len(f.suffixes) >= 3 and "".join(f.suffixes[-3:]).lower() in newtars3:
        return True

    return False


def check_suffix_tar(f: Optional[Path]) -> bool:

    if f is None:
        return False

    if len(f.suffixes) >= 1 and f.suffixes[-1].lower() in tars1:
        return True
    
    if len(f.suffixes) >= 2 and "".join(f.suffixes[-2:]).lower() in tars2:
        return True

    return False


def create(args, shafuncs):
    manager = util.ThreadManager()

    p = manager.add_task(util.tar2pipe, args.target, None, args.verbose, args.dereference, args.excludes, name="tar --> pipe")

    if args.z:
        p = manager.add_task(util.compress_py314, p, None, args.level, args.threads, name="zstd")

    if args.e:
        p = manager.add_task(util.encrypt, p, None, args.k, args.prompt, name="encrypt")

    if len(shafuncs) > 0:
        fork = util.Pipefork(manager.stop_event)
        p4 = fork.fork()
        sha = fork.fork()

        # 从这里把管道流分成两条
        manager.add_task(util.to_pipe, p, fork, name="to pipe")
        manager.add_pipe(fork)
        p = p4

        if args.split is not None and args.sha_file is None:
            sha_file = args.split / "sha.txt"
        else:
            sha_file = args.sha_file

        manager.add_task(util.shasum, shafuncs, sha, sha_file, name="shasum")

    if args.split and (args.f or args.O):
        logger_print.info("--split 和 (-f 或者 -O) 不能同时指定.")
        sys.exit(1)

    with util.open_stream(args.f, "w") as f:

        if args.split:
            manager.task(util.split, p, util.split_prefix(args), args.split_size, args.split, name="split file")
        else:
            manager.add_task(util.to_file, p, f, name="to file")
    
        manager.join_threads()


def extract_not_split(args):

    manager = util.ThreadManager()
    with util.open_stream(args.f, "r") as p:

        # 是从标准输入输出来的
        if args.f is None:
            if args.e:
                p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")


        elif check_suffix_tar(args.f):
            pass
    
        elif check_suffix_newtar(args.f):
            # 自动检测是否解密
            input_key(args)
            print(f"{args.k=}")
            p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")

        else:
            raise tarfile.ReadError(f"未知格式文件: {args.f}")

        try:
            util.extract(p, args.C, args.verbose)
        except tarfile.ReadError:
            logger_print.info("如果从标准输入解压,需要指定 -e 参数。\n可能原因：\n1. 密码错误。\n2. 可以解压格式不对。")
            sys.exit(1)
        
        manager.join_threads()


def extract4split(args):
    """
    解压分割文件
    """
    manager = util.ThreadManager()
    splitter = util.FileSplitterMerger()
    p = manager.add_pipe()
    file = util.merge_prefix(args)
    manager.task(splitter.merge, file.name, args.split, p, name="merge to pipe")

    # 自动检测是否解密
    if check_suffix_newtar(file):
        input_key(args)
        p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")

    try:
        util.extract(p, args.C, args.verbose)
    except tarfile.ReadError:
        logger_print.info("可能原因：\n1. 密码错误。\n2. 可以解压格式不对。")
        sys.exit(1)

    manager.join_threads()


def extract(args):
    """
    解压：
    1. 从文件读取或从标准输入读取。
    2. gz, z2, xz, zst 文件和新的+aes|+aes+split。
    3. 解压时输出只能是路径
    """

    if args.split is not None:
        extract4split(args)
    else:
        extract_not_split(args)


def tarlist4split(args):

    manager = util.ThreadManager()
    splitter = util.FileSplitterMerger()
    p = manager.add_pipe()

    file = util.merge_prefix(args)
    manager.task(splitter.merge, file.name, args.split, p, name="merge file to pipe")

    # 自动检测是否解密
    if check_suffix_newtar(file):
        input_key(args)
        p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")

    try:
        util.tarlist(p, args.verbose)
    except tarfile.ReadError:
        logger_print.info(f"从标准输入解压: {NEWTARS} 需要指定 -e 参数。")
        logger_print.info("可能原因：\n1. 密码错误。\n2. 可以解压格式不对。")
        sys.exit(1)

    manager.join_threads()


def tarlist_not_split(args):

    manager = util.ThreadManager()
    with util.open_stream(args.f, "r") as p:

        # 处理标准输出
        if args.f is None:
            if args.e:
                p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")

        elif check_suffix_tar(args.f):
            pass

        elif check_suffix_newtar(args.f):
            input_key(args)
            p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")
        
        else:
            raise tarfile.ReadError(f"未知格式文件: {args.f}")

        try:
            util.tarlist(p, args.verbose)
        except tarfile.ReadError:
            logger.warning(f"{args.f}: 不是一个tar文件")
            # traceback.print_exc()
            sys.exit(1)

    manager.join_threads()


def tarlist(args):

    if args.split is not None:
        tarlist4split(args)
    else:
        tarlist_not_split(args)


def split_sha(args, shafuncs):
    """从切割的文件计算sha值"""

    if args.split is None:
        logger_print.info("需要指定split目录。")
        sys.exit(1)

    manager = util.ThreadManager()
    splitter = util.FileSplitterMerger()
    p = manager.add_pipe()
    file = util.merge_prefix(args)
    
    manager.task(splitter.merge, file.name, args.split, p, name="merge file to pipe")

    manager.add_task(util.shasum, shafuncs, p, None, name="shasum")

    manager.join_threads()


def input_key(args):
    if args.k:
        password = args.k

    else:
        password = getpass.getpass("Password:")
        if args.c:
            password2 = getpass.getpass("Password(again):")
            if password != password2:
                logger_print.info("password mismatches.")
                sys.exit(2)

    if isinstance(password, str):
        args.k = password.encode("utf-8")
    elif isinstance(password, bytes):
        pass
    else:
        raise ValueError("密码类型不对，需要是 str|bytes。")

def main():
    parse, args = parse_args()

    if args.help:
        parse.print_help()
        sys.exit(0)

    if args.parse:
        logger_print.setLevel(logging.INFO)
        logger_print.info(args)
        sys.exit(0)
    

    if args.verbose >= 1:
        logger_print.setLevel(logging.INFO)

    if args.debug == 1:
        logger.setLevel(logging.INFO)
    elif args.debug == 2:
        logger.setLevel(logging.DEBUG)

    # hash 算计
    shafuncs = set()
    # shafuncs = args.shafuncs # 初步尝试不行
    if args.md5:
        shafuncs |= {"md5"}

    if args.sha1:
        shafuncs |= {"sha1"}

    if args.sha224:
        shafuncs |= {"sha224"}

    if args.sha256:
        shafuncs |= {"sha256"}

    if args.sha384:
        shafuncs |= {"sha384"}

    if args.sha512:
        shafuncs |= {"sha512"}
    
    if args.blake2b:
        shafuncs |= {"blake2b"}
    
    if args.sha_all:
        shafuncs |= set(("md5", "sha1", "sha224", "sha256", "sha384", "sha512", "blake2b"))
    
    if shafuncs == set():
        shafuncs = {"sha256"}
    
    if args.e:
        input_key(args)

    # 创建archive
    if args.c:
        if args.C:
            os.chdir(args.C)

        if len(args.target) == 0:
            logger_print.info(f"{sys.argv[0]}: 谨慎地拒绝创建空归档文件")
            sys.exit(1)

        create(args, shafuncs)

    elif args.x:
        extract(args)

    elif args.list:
        tarlist(args)
    
    elif args.info:

        try:
            util.prompt(args.info)
        except Exception:
            logger_print.info("不是加密文件或文件损坏")
            sys.exit(1)

    elif args.split_sha:
        split_sha(args, shafuncs)

    else:
        logger_print.info("-c|-x|-t|--info|--split-sha 参数之一是必须的")


if __name__ == "__main__":
    main()
    # 使用pyinstaller 打包之后的，logging+stderr,stdout 关闭问题
    # --- 解决方案1 --- 没有生效, 可以还需要配合其他操作,方案2
    # 强制刷新标准输出和标准错误
    # 这样可以避免 Python 在解释器关闭阶段尝试刷新已关闭的流
    try:
        logging.shutdown()
        sys.stdout.flush()
        sys.stderr.flush()
    except ValueError:
        # 忽略已经关闭的文件引起的错误
        pass

    # --- 解决方案2 --- ok
    os._exit(0) # 这里是工程实践上的解决方法

