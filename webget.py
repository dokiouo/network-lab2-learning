"""实验2：仅使用 Python 标准库 socket 实现的 HTTP/1.1 客户端。

GitHub 公有仓库地址：
https://github.com/dokiouo/network-lab2-learning
"""

import socket
import sys
from typing import List, Optional, Tuple


BUFFER_SIZE = 4096
TIMEOUT_SECONDS = 10


def usage() -> None:
    print("Usage: python webget.py host path [port]")


def parse_content_length(header_bytes: bytes) -> Optional[int]:
    """从响应头提取 Content-Length；没有该字段时返回 None。"""
    header_text = header_bytes.decode("iso-8859-1")
    for line in header_text.split("\r\n")[1:]:
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() == "content-length":
            return int(value.strip())
    return None


def receive_response(sock: socket.socket) -> Tuple[bytes, List[int]]:
    """循环接收完整响应，同时记录每次 recv 实际返回的字节数。

    recv 不能只调用一次，因为 TCP 提供的是字节流，一次 recv 只返回
    当前缓冲区中可用的部分数据，并不保证对应一个完整 HTTP 响应。

    循环只有两种结束条件：
    1. 响应头有 Content-Length：收到指定长度的 body 后结束；
    2. 没有 Content-Length：继续接收，直到对端关闭连接，recv 返回 b""。

    请求中使用 Connection: close，保证第二种情况下服务器会关闭连接；
    socket 还设置了 10 秒超时，避免异常服务器一直不关闭导致永久阻塞。
    """
    response = bytearray()
    recv_sizes: List[int] = []
    header_end: Optional[int] = None
    content_length: Optional[int] = None

    while True:
        # 缓冲区大小只是本次最多读取的字节数，不表示一次能收到完整响应。
        chunk = sock.recv(BUFFER_SIZE)
        recv_sizes.append(len(chunk))

        # recv 返回空字节表示 TCP 对端已经正常关闭发送方向。
        if not chunk:
            break

        response.extend(chunk)

        if header_end is None:
            # HTTP 响应头和响应体由第一个空行 \r\n\r\n 分隔。
            marker = response.find(b"\r\n\r\n")
            if marker != -1:
                header_end = marker + 4
                content_length = parse_content_length(bytes(response[:header_end]))

        # 有 Content-Length 时不能等待关闭，而应在 body 收够后立即结束。
        if header_end is not None and content_length is not None:
            body_size = len(response) - header_end
            if body_size >= content_length:
                break

    return bytes(response), recv_sizes


def main() -> int:
    if len(sys.argv) not in (3, 4):
        usage()
        return 2

    host = sys.argv[1]
    path = sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) == 4 else 80
    if not path.startswith("/"):
        path = "/" + path

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Connection: close\r\n"
        "User-Agent: webget-lab2/1.0\r\n"
        "Accept: */*\r\n"
        "\r\n"
    ).encode("ascii")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # 防止服务器既不返回完整内容、也不关闭连接时程序永久等待。
        sock.settimeout(TIMEOUT_SECONDS)
        sock.connect((host, port))
        sock.sendall(request)
        response, recv_sizes = receive_response(sock)

    marker = response.find(b"\r\n\r\n")
    if marker == -1:
        raise RuntimeError("Invalid HTTP response: header terminator not found")

    # T1 要求打印完整响应。这里的目标返回 HTML；若遇到不能按 UTF-8
    # 解码的字节，仅打印时使用替代字符，原始 body 仍按二进制原样保存。
    print("Complete HTTP response:")
    print(response.decode("utf-8", errors="replace"))

    header_bytes = response[:marker]
    body = response[marker + 4 :]
    header_text = header_bytes.decode("iso-8859-1")
    header_lines = header_text.split("\r\n")
    status_parts = header_lines[0].split(" ", 2)
    status_code = status_parts[1] if len(status_parts) > 1 else "unknown"

    print(f"Status code: {status_code}")
    print("Response headers:")
    for line in header_lines[1:]:
        print(line)
    print(f"recv calls: {len(recv_sizes)}")
    print("bytes per recv:", ", ".join(str(size) for size in recv_sizes))

    output_name = "response_body.bin"
    # 必须使用 wb：文本模式可能进行编码或换行转换，破坏图片等二进制数据。
    with open(output_name, "wb") as output:
        output.write(body)
    print(f"Saved {len(body)} body bytes to {output_name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
