"""
一键启动脚本：
1. 启动 cloudflared 命名隧道（固定地址 api.aigin3601.online）
2. 更新 .env 中的 PUBLIC_BASE_URL
3. 重启 Docker 容器使配置生效
4. 持续保持隧道运行（Ctrl+C 退出）
"""

import subprocess
import re
import os
import sys
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
CLOUDFLARED = os.path.join(BASE_DIR, "tools", "cloudflared.exe")

# 固定域名（命名隧道绑定，永不变化）
TUNNEL_NAME = "gd-video"
FIXED_URL = "https://api.aigin3601.online"


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
    """启动命名隧道，返回 process"""
    print(f"[隧道] 正在启动命名隧道 {TUNNEL_NAME}...")
    proc = subprocess.Popen(
        [CLOUDFLARED, "tunnel", "run", TUNNEL_NAME],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    return proc


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
    # 1. 更新 .env（固定地址，无需解析）
    update_env_key("PUBLIC_BASE_URL", FIXED_URL)

    # 2. 重启容器（让新 .env 生效）
    docker_restart()

    # 3. 启动隧道
    proc = run_cloudflared()

    # 4. 打印最终信息
    print("\n" + "=" * 60)
    print("🚀 服务已启动！")
    print(f"   本地地址  : http://localhost:8000")
    print(f"   公网地址  : {FIXED_URL}")
    print(f"   Webhook  : {FIXED_URL}/api/feishu/webhook")
    print("=" * 60)
    print("📋 飞书 Webhook 地址（永久固定，无需再修改）：")
    print(f"   {FIXED_URL}/api/feishu/webhook")
    print("   按 Ctrl+C 关闭隧道并停止服务\n")

    # 5. 持续输出隧道日志
    def on_exit(signum, frame):
        print("\n[退出] 正在关闭隧道...")
        proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_exit)
    signal.signal(signal.SIGTERM, on_exit)

    for line in proc.stdout:
        line = line.rstrip()
        if line:
            print(f"[cloudflared] {line}")

    proc.wait()


if __name__ == "__main__":
    main()
