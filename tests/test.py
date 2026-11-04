import unittest
import subprocess
import os
import shutil
import tempfile
import sys
import io

from pathlib import Path
from unittest.mock import patch

# 配置测试目标
# 可以通过环境变量修改，例如：CMD_TYPE=dist python3 test_tarpy.py
CMD_TYPE = os.getenv("CMD_TYPE", "--tar.py") 
CWD = Path(__file__).resolve().parent.parent

CWD_DIR_IN = os.getenv("CWD_DIR_IN")

CWD_OUT_NOT_CLEAR = os.getenv("CWD_OUT_NOT_CLEAR")


def get_command():
    """根据参数获取要执行的命令"""
    if CMD_TYPE == "--tarpy":
        return ["tarpy"]
    elif CMD_TYPE == "--dist":
        return [CWD / "dist/tarpy"]
    else:
        return [sys.executable, CWD / "src/tar.py"]


class TestTarPy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmd = get_command()
        # 验证命令是否可用
        try:
            if CMD_TYPE == "--tarpy":
                subprocess.run(["type", "tarpy"], check=True, capture_output=True, shell=True)
        except subprocess.CalledProcessError:
            raise unittest.SkipTest("tarpy 命令在系统中不可用")

        """每个测试用例开始前创建临时工作环境"""
        cls.test_root = Path(tempfile.mkdtemp(suffix=".tar-test"))
        print(f"使用的临时输出目录: {cls.test_root}")

        if CWD_DIR_IN and Path(CWD_DIR_IN).is_dir():
            print(f"使用指定的输入目录测试： {CWD_DIR_IN}")
            cls.dir_in = Path(CWD_DIR_IN)
            
        else:
            cls.dir_in = cls.test_root / "dir_in"
            cls.dir_in.mkdir()
            # 创建一些随机测试文件
            for i in range(3):
                with open(cls.dir_in / f"file_{i}.txt", "w") as f:
                    f.write(f"This is test file {i} content. " * 10000)
        
        
        cls.dir_out = cls.test_root / "dir_out"
        cls.dir_out.mkdir()
        

        # 记录生成的 tar 文件路径，方便清理（可选）
        cls.current_tar = None

    @classmethod
    def tearDownClass(cls):
        """每个测试用例结束后清理环境"""
        if cls.test_root.exists() and not CWD_OUT_NOT_CLEAR:
            shutil.rmtree(cls.test_root)

    def run_cmd(self, args, input_data=None, capture_output=True, cwd=None):
        """运行命令的辅助函数"""
        full_args = self.cmd + args
        print(f"执行的命令：{full_args}")
        return subprocess.run(
            full_args,
            input=input_data,
            capture_output=capture_output,
            cwd=cwd,
            text=False # 处理二进制流
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_nested_encrypted_archive_roundtrip(self):
        """加密包的列表和解压应保留嵌套目录、空文件及二进制内容。"""
        source = self.test_root / "nested_source"
        (source / "nested").mkdir(parents=True)
        files = {
            "nested/数据.bin": bytes(range(256)) * 100,
            "nested/empty": b"",
            "text.txt": "测试内容\n".encode(),
        }
        for name, content in files.items():
            (source / name).write_bytes(content)
        archive = self.test_root / "nested.tar.aes"
        output = self.test_root / "nested_output"
        output.mkdir()

        self.assert_success(self.run_cmd(
            ["-ecf", archive, "-k", "password", source.name], cwd=self.test_root
        ))
        listing = self.run_cmd(["-tf", archive, "-k", "password"])
        self.assert_success(listing)
        for name in files:
            # tarfile.list 可转义非 ASCII 字符，Windows 也可能输出反斜杠。
            variants = [name, name.replace("/", "\\")]
            self.assertTrue(
                any(encoded in listing.stdout for variant in variants for encoded in (
                    variant.encode("utf-8"), variant.encode("ascii", "backslashreplace")
                )),
                f"列表中缺少 {name}: {listing.stdout!r}",
            )
        self.assert_success(self.run_cmd(["-xf", archive, "-k", "password", "-C", output]))
        extracted = output / source.name
        for name, content in files.items():
            with self.subTest(name=name):
                self.assertEqual((extracted / name).read_bytes(), content)

    def test_wrong_password_rejected(self):
        """错误密码不能成功解压加密包。"""
        archive = self.test_root / "wrong-password.tar.aes"
        output = self.test_root / "wrong-password-output"
        output.mkdir()
        self.assert_success(self.run_cmd(["-ecf", archive, "-k", "correct", self.dir_in]))
        result = self.run_cmd(["-xf", archive, "-k", "incorrect", "-C", output])
        self.assertNotEqual(result.returncode, 0, "错误密码不应解密成功")

    def test_basic_formats(self):
        """测试基础格式: .tar 和 .tar.zst"""
        formats = [
            (".tar", ["-vcf", "-vxf"]),
            (".tar.zst", ["-zcf", "-zxf"])
        ]
        
        for suffix, flags in formats:
            tar_path = self.test_root / f"test{suffix}"
            tar_out = self.dir_out / suffix
            tar_out.mkdir()
            # 压缩
            res_c = self.run_cmd([flags[0], tar_path, self.dir_in])
            self.assertEqual(res_c.returncode, 0, f"创建 {suffix} 失败")
            
            # 解压
            res_x = self.run_cmd([flags[1], tar_path, "-C", tar_out])
            self.assertEqual(res_x.returncode, 0, f"解压 {suffix} 失败")


    def test_aes_encryption(self):
        """测试 AES 加密格式 .tar.zst.aes"""
        suffix = ".tar.zst.aes"
        tar_path = self.test_root / f"test{suffix}"
        key = "123456"

        # 压缩
        res_c = self.run_cmd(["-k", key, "-ezcf", tar_path, self.dir_in])
        self.assertEqual(res_c.returncode, 0)

        # 查看列表 (tvf)
        res_t = self.run_cmd(["-k", key, "-eztvf", tar_path])
        self.assertEqual(res_t.returncode, 0)

        # 解压
        res_x = self.run_cmd(["-k", key, "-ezxf", tar_path, "-C", self.dir_out])
        self.assertEqual(res_x.returncode, 0)

    def test_pipes_stdin_stdout(self):
        """测试标准输入输出流"""
        key = "123456"

        out_path = self.test_root / "stdin2stdout"
        out_path.mkdir()
        
        # 测试： 压缩到 stdout -> 获取 bytes -> 通过 stdin 解压
        # 对应原脚本: $CMD -ezc $dir_in > $test_tar
        res_c = self.run_cmd(["-k", key, "-ezcf", "-", self.dir_in])
        self.assertEqual(res_c.returncode, 0)
        tar_data = res_c.stdout
        
        # 对应原脚本: cat $test_tar | $CMD -ezx -C $dir_out
        res_x = self.run_cmd(["-k", key, "-ezxf", "-", "-C", out_path], input_data=tar_data)
        self.assertEqual(res_x.returncode, 0)

    def test_system_tar(self):
        """测试对系统 tar 创建的 gz/bz2/xz/zstd 文件的兼容性"""
        for compress_flag, suffix in [("-z", ".tar.gz"), ("-j", ".tar.bz2"), ("-J", ".tar.xz"), ("--zstd", ".tar.zst")]:
            tar_path =  self.test_root / f"GNU-tar{suffix}"
            out_path = self.test_root / f"GNU-tar-out{suffix}"
            out_path.mkdir()
            stdout_path = self.test_root / f"GNU-tar-stdout{suffix}"
            stdout_path.mkdir()
            
            # 使用系统 tar 创建
            subprocess.run(["tar", compress_flag, "-cf", tar_path, self.dir_in], check=True)
            
            # 使用 tarpy 解压文件
            res_x = self.run_cmd(["-xf", tar_path, "-C", out_path])
            self.assertEqual(res_x.returncode, 0, f"解压系统 {suffix} 失败")
            
            # 使用 tarpy 从 stdin 解压
            with open(tar_path, "rb") as f:
                res_stdin = self.run_cmd(["-xf", "-", "-C", stdout_path], input_data=f.read())
            self.assertEqual(res_stdin.returncode, 0, f"从 stdin 解压系统 {suffix} 失败")


    def test_split_merge(self):
        """测试分卷压缩与合并"""
        split_dir = self.test_root / "split_parts"
        split_out = self.test_root / "split_out"
        split_dir.mkdir()
        split_out.mkdir()
        key = "123ji"

        # Split
        res_s = self.run_cmd([
            "-ezc", "--sha512", "--sha256", "-k", key, 
            "--split-size", "1M", "--split", split_dir, self.dir_in
        ])
        self.assertEqual(res_s.returncode, 0)

        # Merge / Extract
        res_m = self.run_cmd([
            "-ezx", "-k", key, "--split", split_dir, 
            self.dir_in, "-C",  split_out
        ])
        self.assertEqual(res_m.returncode, 0)

        # Check SHA
        res_sha = self.run_cmd(["--split-sha", "--split", split_dir])
        self.assertEqual(res_sha.returncode, 0)


class TestAESGCMCompatibility(unittest.TestCase):
    """直接验证加密格式，避免只测试同一进程配置下的往返。"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(CWD / "src"))
        cls.addClassCleanup(sys.path.remove, str(CWD / "src"))
        from libcrypto import AESGCM
        cls.AESGCM = AESGCM

    def encrypt_with_lanes(self, data, lanes):
        output = io.BytesIO()
        with patch("os.cpu_count", return_value=lanes):
            self.AESGCM(b"password", 64).encrypt(io.BytesIO(data), output)
        return output.getvalue()

    def decrypt_with_lanes(self, data, lanes, password=b"password"):
        stream = io.BytesIO(data)
        version = int.from_bytes(stream.read(2), "big")
        output = io.BytesIO()
        with patch("os.cpu_count", return_value=lanes):
            self.AESGCM(password, 64).decrypt(stream, output, version)
        return output.getvalue()

    def test_multichunk_roundtrip(self):
        data = bytes(range(256)) + b"last chunk"
        encrypted = self.encrypt_with_lanes(data, 4)
        self.assertEqual(self.decrypt_with_lanes(encrypted, 4), data)

    def test_authentication_rejects_wrong_password_and_tampering(self):
        from cryptography.exceptions import InvalidTag
        encrypted = self.encrypt_with_lanes(b"authenticated data", 4)
        with self.assertRaises(InvalidTag):
            self.decrypt_with_lanes(encrypted, 4, b"wrong")
        damaged = encrypted[:-1] + bytes([encrypted[-1] ^ 1])
        with self.assertRaises(InvalidTag):
            self.decrypt_with_lanes(damaged, 4)

    def test_v100_archive_decrypts_on_machine_with_different_cpu_count(self):
        """v1.0.0 固定 lanes=4；旧格式不应依赖解密机器的 CPU 数量。"""
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

        def legacy_key(instance, salt, ad):
            return Argon2id(salt=salt, length=32, iterations=13, lanes=4,
                            memory_cost=64 * 1024, ad=ad, secret=None).derive(instance.key)

        data = b"v1.0.0 compatible archive"
        with patch.object(self.AESGCM, "key_Argon2id", legacy_key):
            encrypted = self.encrypt_with_lanes(data, 4)
        self.assertEqual(self.decrypt_with_lanes(encrypted, 8), data)

if __name__ == "__main__":
    unittest.main()
