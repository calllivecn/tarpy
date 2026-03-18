#!/usr/bin/env python3
# coding=utf-8
# Comprehensive unittest for tar.py based on test.sh


import unittest
import subprocess
import tempfile
import shutil
import os
from pathlib import Path
import getpass


# 获取测试脚本所在目录
TEST_DIR = Path(__file__).parent.absolute()
SRC_DIR = TEST_DIR.parent / "src"
TAR_SCRIPT = SRC_DIR / "tar.py"


class TarPyTestCase(unittest.TestCase):
    """基础测试类，提供通用方法"""
    
    @classmethod
    def setUpClass(cls):
        """确保 tar.py 存在"""
        if not TAR_SCRIPT.exists():
            raise FileNotFoundError(f"tar.py 脚本不存在：{TAR_SCRIPT}")
    
    def setUp(self):
        """每个测试前创建临时目录"""
        self.tmpdir = Path(tempfile.mkdtemp(suffix=".tar-test"))
        self.srcdir = self.tmpdir / "src"
        self.srcdir.mkdir()
        self.outdir = self.tmpdir / "out"
        self.outdir.mkdir()
        
        # 创建测试文件结构
        self._create_test_files()
    
    def tearDown(self):
        """每个测试后清理临时目录"""
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def _create_test_files(self):
        """创建测试用的文件结构"""
        (self.srcdir / "file1.txt").write_text("hello world\n", encoding="utf-8")
        (self.srcdir / "file2.txt").write_text("tar.py test\n", encoding="utf-8")
        subdir = self.srcdir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("subdir file\n", encoding="utf-8")
    
    def run_tar(self, args, input_text=None, check=True):
        """
        运行 tar.py 命令
        
        Args:
            args: 命令行参数列表
            input_text: 标准输入文本（用于密码输入）
            check: 是否检查返回码
        
        Returns:
            subprocess.CompletedProcess
        """
        cmd = ["python3", str(TAR_SCRIPT)] + args
        result = subprocess.run(
            cmd,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.tmpdir),
            text=True,
            encoding="utf-8"
        )
        
        if check and result.returncode != 0:
            print(f"命令失败：{' '.join(cmd)}")
            print(f"stderr: {result.stderr}")
        
        return result
    
    def assertFileExists(self, path, msg=None):
        """断言文件存在"""
        self.assertTrue(Path(path).exists(), msg or f"文件不存在：{path}")
    
    def assertFileNotExists(self, path, msg=None):
        """断言文件不存在"""
        self.assertFalse(Path(path).exists(), msg or f"文件应不存在：{path}")
    
    def assertFileContent(self, path, expected_content, msg=None):
        """断言文件内容"""
        content = Path(path).read_text(encoding="utf-8")
        self.assertEqual(content, expected_content, msg or f"文件内容不匹配：{path}")
    
    def verify_extraction(self, extract_dir=None):
        """验证解压后的文件内容"""
        if extract_dir is None:
            extract_dir = self.outdir
        
        self.assertFileExists(extract_dir / "src" / "file1.txt")
        self.assertFileExists(extract_dir / "src" / "file2.txt")
        self.assertFileExists(extract_dir / "src" / "subdir" / "file3.txt")
        
        self.assertFileContent(extract_dir / "src" / "file1.txt", "hello world\n")
        self.assertFileContent(extract_dir / "src" / "file2.txt", "tar.py test\n")
        self.assertFileContent(extract_dir / "src" / "subdir" / "file3.txt", "subdir file\n")


class TestBasicTar(TarPyTestCase):
    """测试基础 tar 功能"""
    
    def test_create_tar(self):
        """测试创建 *.tar 文件"""
        test_tar = self.tmpdir / "test.tar"
        result = self.run_tar(["-vcf", str(test_tar), str(self.srcdir)])
        self.assertEqual(result.returncode, 0, f"创建 tar 失败：{result.stderr}")
        self.assertFileExists(test_tar)
    
    def test_extract_tar(self):
        """测试解压 *.tar 文件"""
        test_tar = self.tmpdir / "test.tar"
        
        # 创建
        self.run_tar(["-cf", str(test_tar), str(self.srcdir)])
        
        # 解压
        result = self.run_tar(["-vxf", str(test_tar), "-C", str(self.outdir)])
        self.assertEqual(result.returncode, 0, f"解压 tar 失败：{result.stderr}")
        self.verify_extraction()
    
    def test_create_and_extract_tar(self):
        """测试创建并解压 *.tar 文件"""
        test_tar = self.tmpdir / "test.tar"
        
        # 创建
        result = self.run_tar(["-vcf", str(test_tar), str(self.srcdir)])
        self.assertEqual(result.returncode, 0)
        
        # 解压
        result = self.run_tar(["-vxf", str(test_tar), "-C", str(self.outdir)])
        self.assertEqual(result.returncode, 0)
        self.verify_extraction()


class TestZstdCompression(TarPyTestCase):
    """测试 zstd 压缩功能"""
    
    def test_create_tar_zst(self):
        """测试创建 *.tar.zst 文件"""
        test_tar = self.tmpdir / "test.tar.zst"
        result = self.run_tar(["-zcf", str(test_tar), str(self.srcdir)])
        self.assertEqual(result.returncode, 0, f"创建 tar.zst 失败：{result.stderr}")
        self.assertFileExists(test_tar)
    
    def test_extract_tar_zst(self):
        """测试解压 *.tar.zst 文件"""
        test_tar = self.tmpdir / "test.tar.zst"
        
        # 创建
        self.run_tar(["-zcf", str(test_tar), str(self.srcdir)])
        
        # 解压
        result = self.run_tar(["-zxf", str(test_tar), "-C", str(self.outdir)])
        self.assertEqual(result.returncode, 0, f"解压 tar.zst 失败：{result.stderr}")
        self.verify_extraction()
    
    def test_create_and_extract_tar_zst(self):
        """测试创建并解压 *.tar.zst 文件"""
        test_tar = self.tmpdir / "test.tar.zst"
        
        # 创建
        result = self.run_tar(["-zcf", str(test_tar), str(self.srcdir)])
        self.assertEqual(result.returncode, 0)
        
        # 解压
        result = self.run_tar(["-zxf", str(test_tar), "-C", str(self.outdir)])
        self.assertEqual(result.returncode, 0)
        self.verify_extraction()


class TestEncryption(TarPyTestCase):
    """测试加密功能"""
    
    PASSWORD = "123456"
    
    def test_create_encrypted_ta(self):
        """测试创建 *.tar.aes (.ta) 文件"""
        test_tar = self.tmpdir / "test.ta"
        password_input = f"{self.PASSWORD}\n{self.PASSWORD}\n"
        
        result = self.run_tar(
            ["-ecf", str(test_tar), str(self.srcdir)],
            input_text=password_input
        )
        self.assertEqual(result.returncode, 0, f"创建加密文件失败：{result.stderr}")
        self.assertFileExists(test_tar)
    
    def test_extract_encrypted_ta(self):
        """测试解压 *.tar.aes (.ta) 文件"""
        test_tar = self.tmpdir / "test.ta"
        password_input = f"{self.PASSWORD}\n{self.PASSWORD}\n"
        
        # 创建
        self.run_tar(["-ecf", str(test_tar), str(self.srcdir)], input_text=password_input)
        
        # 解压
        result = self.run_tar(
            ["-exf", str(test_tar), "-C", str(self.outdir)],
            input_text=f"{self.PASSWORD}\n"
        )
        self.assertEqual(result.returncode, 0, f"解压加密文件失败：{result.stderr}")
        self.verify_extraction()
    
    def test_create_encrypted_tza(self):
        """测试创建 *.tar.zst.aes (.tza) 文件"""
        test_tar = self.tmpdir / "test.tza"
        password_input = f"{self.PASSWORD}\n{self.PASSWORD}\n"
        
        result = self.run_tar(
            ["-ezcf", str(test_tar), str(self.srcdir)],
            input_text=password_input
        )
        self.assertEqual(result.returncode, 0, f"创建压缩加密文件失败：{result.stderr}")
        self.assertFileExists(test_tar)
    
    def test_extract_encrypted_tza(self):
        """测试解压 *.tar.zst.aes (.tza) 文件"""
        test_tar = self.tmpdir / "test.tza"
        password_input = f"{self.PASSWORD}\n{self.PASSWORD}\n"
        
        # 创建
        self.run_tar(["-ezcf", str(test_tar), str(self.srcdir)], input_text=password_input)
        
        # 解压
        result = self.run_tar(
            ["-ezxf", str(test_tar), "-C", str(self.outdir)],
            input_text=f"{self.PASSWORD}\n"
        )
        self.assertEqual(result.returncode, 0, f"解压压缩加密文件失败：{result.stderr}")
        self.verify_extraction()
    
    def test_wrong_password(self):
        """测试错误密码"""
        test_tar = self.tmpdir / "test.tza"
        
        # 创建
        password_input = f"{self.PASSWORD}\n{self.PASSWORD}\n"
        self.run_tar(["-ezcf", str(test_tar), str(self.srcdir)], input_text=password_input)
        
        # 用错误密码解压
        result = self.run_tar(
            ["-ezxf", str(test_tar), "-C", str(self.outdir)],
            input_text="wrongpassword\n",
            check=False
        )
        self.assertNotEqual(result.returncode, 0, "错误密码应该失败")


class TestStdio(TarPyTestCase):
    """测试标准输入输出功能"""
    
    PASSWORD = "123456"
    
    def test_create_to_stdout_tar_zst_aes(self):
        """测试从标准输出创建 *.tar.zst.aes"""
        test_tar = self.tmpdir / "test.tar.zst.aes"
        password_input = f"{self.PASSWORD}\n{self.PASSWORD}\n"
        
        # 创建到标准输出
        result = self.run_tar(
            ["-k", self.PASSWORD, "-ezc", str(self.srcdir)],
            input_text=password_input
        )
        self.assertEqual(result.returncode, 0)
        
        # 写入文件
        test_tar.write_bytes(result.stdout.encode("latin-1"))
        self.assertFileExists(test_tar)
    
    def test_extract_from_stdin_tar_zst_aes(self):
        """测试从标准输入解压 *.tar.zst.aes"""
        test_tar = self.tmpdir / "test.tar.zst.aes"
        
        # 先创建文件
        password_input = f"{self.PASSWORD}\n{self.PASSWORD}\n"
        self.run_tar(["-k", self.PASSWORD, "-ezcf", str(test_tar), str(self.srcdir)],
                    input_text=password_input)
        
        # 从标准输入解压
        with open(test_tar, "rb") as f:
            result = subprocess.run(
                ["python3", str(TAR_SCRIPT), "-k", self.PASSWORD, "-ezx", "-C", str(self.outdir)],
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.tmpdir),
                text=True
            )
        
        self.assertEqual(result.returncode, 0, f"从标准输入解压失败：{result.stderr}")
        self.verify_extraction()
    
    def test_create_to_stdout_tar_aes(self):
        """测试从标准输出创建 *.tar.aes"""
        test_tar = self.tmpdir / "test.tar.aes"
        
        # 创建到标准输出
        result = self.run_tar(
            ["-k", self.PASSWORD, "-ec", str(self.srcdir)],
            input_text=f"{self.PASSWORD}\n{self.PASSWORD}\n"
        )
        self.assertEqual(result.returncode, 0)
        
        # 写入文件
        test_tar.write_bytes(result.stdout.encode("latin-1"))
        self.assertFileExists(test_tar)
    
    def test_extract_from_stdin_tar_aes(self):
        """测试从标准输入解压 *.tar.aes"""
        test_tar = self.tmpdir / "test.tar.aes"
        
        # 先创建文件
        self.run_tar(["-k", self.PASSWORD, "-ecf", str(test_tar), str(self.srcdir)],
                    input_text=f"{self.PASSWORD}\n{self.PASSWORD}\n")
        
        # 从标准输入解压
        with open(test_tar, "rb") as f:
            result = subprocess.run(
                ["python3", str(TAR_SCRIPT), "-k", self.PASSWORD, "-ex", "-C", str(self.outdir)],
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.tmpdir),
                text=True
            )
        
        self.assertEqual(result.returncode, 0, f"从标准输入解压失败：{result.stderr}")
        self.verify_extraction()


class TestListContents(TarPyTestCase):
    """测试查看归档内容功能"""
    
    PASSWORD = "123456"
    
    def test_list_tar(self):
        """测试列出 *.tar 内容"""
        test_tar = self.tmpdir / "test.tar"
        
        # 创建
        self.run_tar(["-cf", str(test_tar), str(self.srcdir)])
        
        # 列表
        result = self.run_tar(["-tvf", str(test_tar)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("file1.txt", result.stdout)
        self.assertIn("file2.txt", result.stdout)
    
    def test_list_tza(self):
        """测试列出 *.tza 内容"""
        test_tar = self.tmpdir / "test.tza"
        
        # 创建
        self.run_tar(
            ["-k", self.PASSWORD, "-ezcf", str(test_tar), str(self.srcdir)],
            input_text=f"{self.PASSWORD}\n{self.PASSWORD}\n"
        )
        
        # 列表
        result = self.run_tar(
            ["-k", self.PASSWORD, "-eztvf", str(test_tar)],
            input_text=f"{self.PASSWORD}\n"
        )
        self.assertEqual(result.returncode, 0, f"列出 tza 内容失败：{result.stderr}")
        self.assertIn("file1.txt", result.stdout)


class TestSystemTarFormats(TarPyTestCase):
    """测试系统 tar 格式兼容性"""
    
    def setUp(self):
        """检查系统 tar 命令是否存在"""
        super().setUp()
        result = subprocess.run(["tar", "--version"], capture_output=True)
        if result.returncode != 0:
            self.skipTest("系统 tar 命令不可用")
    
    def test_extract_tar_gz(self):
        """测试解压 *.tar.gz"""
        test_tar = self.tmpdir / "test.tar.gz"
        
        # 使用系统 tar 创建
        subprocess.run(["tar", "-zcf", str(test_tar), "-C", str(self.srcdir.parent), "src"],
                      check=True)
        
        # 使用 tar.py 解压
        result = self.run_tar(["-xf", str(test_tar), "-C", str(self.outdir)])
        self.assertEqual(result.returncode, 0, f"解压 tar.gz 失败：{result.stderr}")
        self.verify_extraction()
    
    def test_extract_from_stdin_tar_gz(self):
        """测试从标准输入解压 *.tar.gz"""
        test_tar = self.tmpdir / "test.tar.gz"
        
        # 使用系统 tar 创建
        subprocess.run(["tar", "-zcf", str(test_tar), "-C", str(self.srcdir.parent), "src"],
                      check=True)
        
        # 从标准输入解压
        with open(test_tar, "rb") as f:
            result = subprocess.run(
                ["python3", str(TAR_SCRIPT), "-x", "-C", str(self.outdir)],
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.tmpdir),
                text=True
            )
        
        self.assertEqual(result.returncode, 0, f"从标准输入解压 tar.gz 失败：{result.stderr}")
        self.verify_extraction()
    
    def test_extract_tar_bz2(self):
        """测试解压 *.tar.bz2"""
        test_tar = self.tmpdir / "test.tar.bz2"
        
        # 使用系统 tar 创建
        subprocess.run(["tar", "-jcf", str(test_tar), "-C", str(self.srcdir.parent), "src"],
                      check=True)
        
        # 使用 tar.py 解压
        result = self.run_tar(["-xf", str(test_tar), "-C", str(self.outdir)])
        self.assertEqual(result.returncode, 0, f"解压 tar.bz2 失败：{result.stderr}")
        self.verify_extraction()
    
    def test_extract_from_stdin_tar_bz2(self):
        """测试从标准输入解压 *.tar.bz2"""
        test_tar = self.tmpdir / "test.tar.bz2"
        
        # 使用系统 tar 创建
        subprocess.run(["tar", "-jcf", str(test_tar), "-C", str(self.srcdir.parent), "src"],
                      check=True)
        
        # 从标准输入解压
        with open(test_tar, "rb") as f:
            result = subprocess.run(
                ["python3", str(TAR_SCRIPT), "-x", "-C", str(self.outdir)],
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.tmpdir),
                text=True
            )
        
        self.assertEqual(result.returncode, 0, f"从标准输入解压 tar.bz2 失败：{result.stderr}")
        self.verify_extraction()
    
    def test_extract_tar_xz(self):
        """测试解压 *.tar.xz"""
        test_tar = self.tmpdir / "test.tar.xz"
        
        # 使用系统 tar 创建
        subprocess.run(["tar", "-Jcf", str(test_tar), "-C", str(self.srcdir.parent), "src"],
                      check=True)
        
        # 使用 tar.py 解压
        result = self.run_tar(["-xf", str(test_tar), "-C", str(self.outdir)])
        self.assertEqual(result.returncode, 0, f"解压 tar.xz 失败：{result.stderr}")
        self.verify_extraction()
    
    def test_extract_from_stdin_tar_xz(self):
        """测试从标准输入解压 *.tar.xz"""
        test_tar = self.tmpdir / "test.tar.xz"
        
        # 使用系统 tar 创建
        subprocess.run(["tar", "-Jcf", str(test_tar), "-C", str(self.srcdir.parent), "src"],
                      check=True)
        
        # 从标准输入解压
        with open(test_tar, "rb") as f:
            result = subprocess.run(
                ["python3", str(TAR_SCRIPT), "-x", "-C", str(self.outdir)],
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.tmpdir),
                text=True
            )
        
        self.assertEqual(result.returncode, 0, f"从标准输入解压 tar.xz 失败：{result.stderr}")
        self.verify_extraction()


class TestSplitMerge(TarPyTestCase):
    """测试 split + merge 功能"""
    
    PASSWORD = "123ji"
    
    def test_split_create_encrypted(self):
        """测试创建加密 + 分割文件"""
        split_dir = self.tmpdir / "split"
        split_dir.mkdir()
        
        result = self.run_tar([
            "-ezc",
            "--sha512", "--sha256",
            "-k", self.PASSWORD,
            "--split-size", "50M",
            "--split", str(split_dir),
            str(self.srcdir)
        ])
        
        self.assertEqual(result.returncode, 0, f"创建分割文件失败：{result.stderr}")
        # 检查分割目录中是否有文件
        split_files = list(split_dir.glob("*"))
        self.assertTrue(len(split_files) > 0, "分割目录应该包含文件")
    
    def test_split_merge_encrypted(self):
        """测试解压加密 + 分割文件"""
        split_dir = self.tmpdir / "split"
        split_dir.mkdir()
        
        # 创建分割文件
        self.run_tar([
            "-ezc",
            "-k", self.PASSWORD,
            "--split-size", "50M",
            "--split", str(split_dir),
            str(self.srcdir)
        ])
        
        # 解压分割文件
        result = self.run_tar([
            "-ezx",
            "-k", self.PASSWORD,
            "--split", str(split_dir),
            "-C", str(self.outdir)
        ])
        
        self.assertEqual(result.returncode, 0, f"解压分割文件失败：{result.stderr}")
        self.verify_extraction()
    
    def test_split_create_and_merge(self):
        """测试完整的创建 + 解压分割文件流程"""
        split_dir = self.tmpdir / "split"
        split_dir.mkdir()
        
        # 创建
        result = self.run_tar([
            "-ezc",
            "--sha512", "--sha256",
            "-k", self.PASSWORD,
            "--split-size", "50M",
            "--split", str(split_dir),
            str(self.srcdir)
        ])
        self.assertEqual(result.returncode, 0)
        
        # 解压
        result = self.run_tar([
            "-ezx",
            "-k", self.PASSWORD,
            "--split", str(split_dir),
            "-C", str(self.outdir)
        ])
        self.assertEqual(result.returncode, 0)
        self.verify_extraction()


class TestSplitSha(TarPyTestCase):
    """测试 --split-sha 功能"""
    
    PASSWORD = "123ji"
    
    def test_split_sha(self):
        """测试从 split 目录计算 sha 值"""
        split_dir = self.tmpdir / "split"
        split_dir.mkdir()
        
        # 先创建分割文件
        self.run_tar([
            "-ezc",
            "-k", self.PASSWORD,
            "--split-size", "50M",
            "--split", str(split_dir),
            str(self.srcdir)
        ])
        
        # 计算 sha
        result = self.run_tar([
            "--split-sha",
            "--split", str(split_dir)
        ])
        
        self.assertEqual(result.returncode, 0, f"计算 split sha 失败：{result.stderr}")


class TestVerboseAndDebug(TarPyTestCase):
    """测试 verbose 和 debug 选项"""
    
    def test_verbose_create(self):
        """测试 verbose 模式创建"""
        test_tar = self.tmpdir / "test.tar"
        result = self.run_tar(["-vcf", str(test_tar), str(self.srcdir)])
        self.assertEqual(result.returncode, 0)
        # verbose 模式应该有输出
        self.assertTrue(len(result.stdout) > 0 or len(result.stderr) > 0)
    
    def test_verbose_extract(self):
        """测试 verbose 模式解压"""
        test_tar = self.tmpdir / "test.tar"
        
        # 创建
        self.run_tar(["-cf", str(test_tar), str(self.srcdir)])
        
        # verbose 解压
        result = self.run_tar(["-vxf", str(test_tar), "-C", str(self.outdir)])
        self.assertEqual(result.returncode, 0)
    
    def test_debug_mode(self):
        """测试 debug 模式"""
        test_tar = self.tmpdir / "test.tar"
        result = self.run_tar(["-vcf", str(test_tar), str(self.srcdir)])
        self.assertEqual(result.returncode, 0)


class TestEdgeCases(TarPyTestCase):
    """测试边界情况"""
    
    PASSWORD = "123456"
    
    def test_empty_archive_rejected(self):
        """测试拒绝创建空归档"""
        result = self.run_tar(["-cf", "/dev/null"], check=False)
        # 应该拒绝创建空归档
        self.assertNotEqual(result.returncode, 0)
    
    def test_nonexistent_input_dir(self):
        """测试不存在的输入目录"""
        test_tar = self.tmpdir / "test.tar"
        nonexistent = self.tmpdir / "nonexistent"
        result = self.run_tar(["-cf", str(test_tar), str(nonexistent)], check=False)
        self.assertNotEqual(result.returncode, 0)
    
    def test_unknown_format_file(self):
        """测试未知格式文件"""
        unknown_file = self.tmpdir / "test.unknown"
        unknown_file.write_text("not a tar file")
        result = self.run_tar(["-xf", str(unknown_file), "-C", str(self.outdir)], check=False)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
