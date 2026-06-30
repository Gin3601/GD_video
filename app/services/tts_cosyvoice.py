"""
CosyVoice2 旁白生成模块（骨架）
本地 TTS 模型，质量高、支持零样本音色克隆，但 CPU 推理偏慢。

【前置步骤】使用前需手动完成：

1. 准备 Python 3.10 或 3.11 的环境（Python 3.13 上 PyTorch 生态目前还不完整）

2. 安装依赖：
       pip install modelscope torch torchaudio onnxruntime
       pip install -U funasr

3. 从 ModelScope 下载模型到项目下的 models/ 目录：
       modelscope download --model iic/CosyVoice2-0.5B --local_dir ./models/CosyVoice2-0.5B

4. 准备一段 3~10 秒的参考音频（决定克隆出来的音色），
   放在 morning_video/voiceovers/ 下，例如 my_voice_sample.wav

5. today.json 配置示例：
       "voiceover": "cosyvoice"
       "voice": "voiceovers/my_voice_sample.wav"

【CPU 推理速度参考】
   i5-14600K 上，生成 15 秒中文音频约需 30~90 秒。
"""

from pathlib import Path

# 模型默认位置（相对项目根目录）
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "models" / "CosyVoice2-0.5B"


def _missing_deps_message() -> str:
    return (
        "\n" + "=" * 60 + "\n"
        "错误：CosyVoice2 依赖未安装或不完整\n\n"
        "请在 Python 3.10/3.11 环境中执行：\n"
        "    pip install modelscope torch torchaudio onnxruntime\n"
        "    pip install -U funasr\n\n"
        "然后下载模型：\n"
        "    modelscope download --model iic/CosyVoice2-0.5B "
        "--local_dir ./models/CosyVoice2-0.5B\n\n"
        "如需快速回退，请把 today.json 的 voiceover 改为 \"edge\"\n"
        + "=" * 60
    )


def synthesize_cosyvoice(text: str, prompt_wav: str, output_path: Path) -> bool:
    """
    用 CosyVoice2 克隆指定参考音频的音色，朗读 text。
    成功返回 True，失败返回 False。
    """
    if not text.strip():
        print("跳过旁白：文案为空")
        return False

    if not prompt_wav:
        print("错误：cosyvoice 模式必须在 today.json 中通过 voice 字段指定参考音频路径")
        print("示例：\"voice\": \"voiceovers/my_voice_sample.wav\"")
        return False

    prompt_path = Path(prompt_wav)
    if not prompt_path.is_absolute():
        prompt_path = Path(__file__).resolve().parent / prompt_wav
    if not prompt_path.exists():
        print(f"错误：参考音频不存在：{prompt_path}")
        return False

    if not DEFAULT_MODEL_DIR.exists():
        print(f"错误：CosyVoice2 模型未下载，期望路径：{DEFAULT_MODEL_DIR}")
        print(_missing_deps_message())
        return False

    # ---- lazy import，避免依赖缺失时影响主流程 ----
    try:
        import torch  # noqa: F401
        import torchaudio
        # CosyVoice 官方推理类，按官方 README 路径导入
        # （cosyvoice 仓库的 cosyvoice.cli.cosyvoice 模块）
        from cosyvoice.cli.cosyvoice import CosyVoice2
        from cosyvoice.utils.file_utils import load_wav
    except ImportError as e:
        print(f"导入失败：{e}")
        print(_missing_deps_message())
        return False

    try:
        print(f"正在加载 CosyVoice2 模型（首次加载较慢，约 10~30 秒）...")
        model = CosyVoice2(str(DEFAULT_MODEL_DIR))

        print(f"加载参考音频：{prompt_path}")
        prompt_speech = load_wav(str(prompt_path), 16000)

        print(f"正在合成旁白（CosyVoice2，CPU 推理约需 30~90 秒）...")
        # 零样本音色克隆：text=要说的话, prompt_text 可留空, prompt_speech=参考音色
        speeches = []
        for out in model.inference_zero_shot(text, "", prompt_speech, stream=False):
            speeches.append(out["tts_speech"])

        if not speeches:
            print("警告：CosyVoice2 未返回音频")
            return False

        # 拼接多段输出（一般只有一段）并保存
        audio = torch.cat(speeches, dim=1)
        torchaudio.save(str(output_path), audio, model.sample_rate)

        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"旁白生成完成：{output_path}")
            return True
        print("警告：CosyVoice2 输出文件为空")
        return False
    except Exception as e:
        print(f"警告：CosyVoice2 生成失败（{type(e).__name__}: {e}），跳过旁白")
        return False
