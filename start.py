"""
一键启动脚本：
1. 启动 cloudflared 隧道，自动获取公网地址
2. 更新 .env 中的 PUBLIC_BASE_URL
3. 重启 Docker 容器使配置生效
4. 持续保持隧道运行（Ctrl+C 退出）
"""

import subprocess
import re
import os
import sys
import time
import threading
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
CLOUDFLARED = os.path.join(BASE_DIR, "tools", "cloudflared.exe")


def update_env_key(key, value):
    """更新 .env 文件中的某个 KEY=VALUE"""
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(r"^" + re.escape(key) + r"=.*$", re.MULTILINE)
    new_line = key + "=" + value
    if pattern.search(content):
        content = pattern.sub(new_line, content)
    else:
        content = content.rstrip("\n") + "\n" + new_line + "\n"
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[ENV] {key} = {value}")


def run_cloudflared():
    """启动 cloudflared，返回 (process, tunnel_url)"""
    print("[隧道] 正在启动 Cloudflare 隧道...")
    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    tunnel_url = None
    url_event = threading.Event()

    def reader():
        nonlocal tunnel_url
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                print(f"[cloudflared] {line}")
            m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if m and not tunnel_url:
                tunnel_url = m.group(0)
                url_event.set()

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    # 等待最多 30 秒获取地址
    if not url_event.wait(timeout=30):
        proc.terminate()
        raise RuntimeError("[错误] 未能在 30 秒内获取隧道地址，请检查网络")

    return proc, tunnel_url


def docker_restart():
    """重启 Docker 容器"""
    print("[Docker] 正在重启容器...")
    result = subprocess.run(
        ["docker", "compose", "restart"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 or "Started" in (result.stdout + result.stderr):
        print("[Docker] 容器已重启")
    else:
        print(f"[Docker] 重启输出: {result.stdout} {result.stderr}")


def main():
    # 1. 启动隧道
    proc, tunnel_url = run_cloudflared()

    # 2. 更新 .env
    update_env_key("PUBLIC_BASE_URL", tunnel_url)
    print(f"\n✅ 公网地址: {tunnel_url}")
    print(f"✅ Webhook 地址: {tunnel_url}/api/feishu/webhook\n")

    # 3. 重启容器
    docker_restart()

    # 4. 打印最终信息
    print("\n" + "=" * 60)
    print("🚀 服务已启动！")
    print(f"   本地地址  : http://localhost:8000")
    print(f"   公网地址  : {tunnel_url}")
    print(f"   Webhook  : {tunnel_url}/api/feishu/webhook")
    print("=" * 60)
    print("📋 请将 Webhook 地址填入飞书多维表格自动化配置中")
    print("   按 Ctrl+C 关闭隧道并停止服务\n")

    # 5. 保持运行，处理退出
    def on_exit(signum, frame):
        print("\n[退出] 正在关闭隧道...")
        proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_exit)
    signal.signal(signal.SIGTERM, on_exit)

    proc.wait()


if __name__ == "__main__":
    main()
