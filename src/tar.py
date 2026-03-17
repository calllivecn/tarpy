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

import util
from libargparse import parse_args
from logs import logger, logger_print


NEWTARS = (".tar.aes", ".tar.zst.aes", ".ta", ".tza")
TARFILE = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tbz", ".tar.xz", ".txz", ".tar.zst", ".tz")


def create(args, shafuncs):
    manager = util.ThreadManager()

    p = manager.add_task(util.tar2pipe, args.target, None, args.verbose, args.excludes, name="tar --> pipe")

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

    suffixs = args.f.suffixes
    suffix = "".join(suffixs).lower()

    with util.open_stream(args.f, "r") as f:
        # 解压*.tar.gz *.tar.xz *.tar.bz2 *.tar.zst
        if suffix in TARFILE:
            try:
                util.extract(f, args.C, args.verbose)
            except tarfile.ReadError:
                logger.warning(f"{args.f}: 不是一个tar文件")
                sys.exit(0)
    
        # 解压后缀：NEWTARS
        elif suffix in NEWTARS:
            manager = util.ThreadManager()

            p = manager.add_task(util.to_pipe, f, None, name="to pipe")

            # if args.e:
            # 自动检测是否解密
            if suffix in (".tar.zst.aes", ".tz", ".tza"):
                input_key(args)
                p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")
    
            # if args.z:
            #     p = manager.add_task(util.decompress, p, None, name="decompress")
    
            try:
                util.extract(p, args.C, args.verbose)
            except tarfile.ReadError:
                # logger_print.info(f"解压: {NEWTARS} 需要指定，-z|-e 参数。")
                logger_print.info(f"解压: {NEWTARS} 需要指定，-e 参数。")
                logger_print.info("可能原因：\n1. 密码错误。\n2. 可以解压格式不对。")
                sys.exit(1)

            manager.join_threads()
        
        else:
            raise tarfile.ReadError(f"未知格式文件: {args.f}")



def extract4split(args):
    """
    解压分割文件
    """
    # 解压后缀：*.tar.zst, *.tar.zst.aes, *.tz, *.tza

    manager = util.ThreadManager()
    file = util.merge_prefix(args)

    if args.split:
        splitter = util.FileSplitterMerger()
        p = manager.add_task(splitter.merge, file.name, args.split, None, name="merge to pipe")
    else:
        p = manager.add_pipe()

    # 自动检测是否解密
    if file.suffix in (".tz", ".tza"):
        input_key(args)
        p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")
    

    # if args.z:
    #     p = manager.add_task(util.decompress, p, None, name="decompress")
    
    try:
        util.extract(p, args.C, args.verbose)
    except tarfile.ReadError:
        logger_print.info(f"解压: {NEWTARS} 需要指定 -e 参数。")
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


def tarlist_not_split(args, suffix: str):
    """
    处理 NESTARS 文件
    """

    manager = util.ThreadManager()
    with util.open_stream(args.f, "r") as f:

        p = manager.add_task(util.to_pipe, f, None, name="tarlist4file")

        if suffix not in NEWTARS:
            raise tarfile.ReadError("未知格式文件")
    
        if suffix in (".tar.zst.aes", ".tza", ".ta"):
            input_key(args)
            p = manager.add_task(util.decrypt, p, None, args.k, name="decrypt")

        try:
            util.tarlist(p, args.verbose)
        except tarfile.ReadError:
            logger.warning(f"{args.f}: 不是一个tar文件")
            # traceback.print_exc()
            sys.exit(1)


def tarlist4split(args):

    manager = util.ThreadManager()
    splitter = util.FileSplitterMerger()
    p = manager.add_pipe()

    # filename = util.split_prefix(args)
    # manager.task(splitter.merge, filename, args.split, p, name="merge file to pipe")
    file = util.merge_prefix(args)
    manager.task(splitter.merge, file.name, args.split, p, name="merge file to pipe")

    # 自动检测是否解密
    if file.suffix in (".tz", ".tza"):
        input_key(args)
        p = manager.add_task(util.decrypt, p, None, args.k)
    
    # if args.z:
    #     p = manager.add_task(util.decompress, p, None, name="decompress")
    
    try:
        util.tarlist(p, args.verbose)
    except tarfile.ReadError:
        logger_print.info(f"从标准输入解压: {NEWTARS} 需要指定，-z|-e 参数。")
        logger_print.info("可能原因：\n1. 密码错误。\n2. 可以解压格式不对。")
        sys.exit(1)

    manager.join_threads()


def tarlist(args):

    if args.split is not None:
        tarlist4split(args)

    else:
        suffixs = args.f.suffixes
        suffix = "".join(suffixs).lower()

        if suffix in NEWTARS:
            tarlist_not_split(args, suffix)

        elif suffix in TARFILE:
            try:
                util.tarlist(args.f, args.verbose)
            except tarfile.ReadError:
                logger.warning("当前输入, 不是一个tar文件")
                sys.exit(0)

        else:
            raise tarfile.ReadError(f"未知格式文件: {args.f}")


def split_sha(args, shafuncs):
    """从切割的文件计算sha值"""

    if args.split is None:
        logger_print.info("需要指定split目录。")
        sys.exit(1)

    manager = util.ThreadManager()
    splitter = util.FileSplitterMerger()

    p = manager.add_pipe()
    manager.task(splitter.merge, args.split_prefix, args.split, p, name="merge file to pipe")

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

    args.k = password.encode("utf-8")


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

