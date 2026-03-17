# 实现过程中的设想，测试，遇到的问题，和解决方案。


```s
怎么实现一种管道式的处理流?

实现像类似shell 管理 的处理的效果，处其他处理可以，随机需要增加，或减少。
tar() | zstd() | aes() | --> hash() --> sha result --> end()
                       \
                        \ --> split() -- > file result --> end()
```

- tarfile.open() 需要 fileobj 需要包装一下。
- pipe 是两个FD 需要 关闭两次。 写关闭时: read() -> b""

```py
class PIPE:

    def __init__(self):
        self.r, self.w = os.pipe()
    
    def read(self, size):
        return os.read(self.r, size)

    def write(self, data):
        return os.write(self.w, data)
    
    def close(self):
        os.close(self.w)
    
    def close2(self):
        os.close(self.r)
```


- 例如：在处理几十GB的日志压缩包下载流时，边下载边解压，不把整个文件保存到本地硬盘：

```py
import tarfile
import requests

response = requests.get("http://example.com/huge-logs.tar.gz", stream=True)
# 用 r|gz 模式直接读取 HTTP 响应流 (response.raw)
with tarfile.open(fileobj=response.raw, mode="r|gz") as tar:
    for member in tar:
        if member.name.endswith(".log"):
            f = tar.extractfile(member)
            # 处理日志数据... 
            # 注意：处理完毕后该 member 即从内存释放，无法再次访问
```


## 记录

- 果 dereference 为 False，则会将符号链接和硬链接添加到归档中。
- 如果为 True，则会将目标文件的内容添加到归档中。在不支持符号链接的系统上参数将不起作用。

- 在 tarfile 模块中，普通模式（Normal Mode，如 r:、w:gz）和流模式（Stream Mode，如 r|、w|gz）的核心区别在于对底层文件对象是否要求支持“随机访问（Seekable）”。
