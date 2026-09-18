#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract.py — 视频知识提取、语音转录与证据提炼引擎 (v3.0)

核心功能：
  1. 五级 Token 极简漏斗：
     - L0 导航：秒级字幕快车道 (pick_subtitle) 与视频章节指纹 (chapters)
     - L0-B 侦察：无字幕时采样各切片 20s 音频，用 tiny 模型毫秒级粗转录 (scout)
     - L1 目标切片：支持 --chunks 仅转录命中的核心章节
     - L1.5 证据提炼：--evidence 模式过滤铺垫过渡，提炼关键定理、代码与陷阱原句
  2. 健壮的音频与模型路由：
     - 自动检测本地音视频文件，免网络调用
     - 优先命中本地音频与 16kHz WAV 缓存，带 decodable 完整性探针
     - Faster-Whisper 模型支持 ModelScope 国内源 + 阿里 DoH 真实 IP 钉扎抵御代理劫持
     - 推理层 GPU/CUDA OOM 自动捕获并无缝回退至 CPU int8
  3. 双语技术术语偏置：
     - 内置通用计算机科学与工程提示词，支持 --domain-prompt 补充专业术语
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import site
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from tqdm import tqdm
except ImportError:
    class tqdm:  # noqa: N801
        def __init__(self, iterable=None, **kw):
            self._it = iterable
            self.n = 0
            self.total = kw.get("total", 0)
            desc = kw.get("desc", "")
            if desc:
                print(f"[progress] {desc} start", file=sys.stderr)

        def __iter__(self):
            return iter(self._it or [])

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def update(self, n=1):
            self.n += n

        def close(self):
            pass

        def set_postfix_str(self, s):
            pass


APP = "video2obsidian"
CACHE_ROOT = Path(os.environ.get("V2N_CACHE", Path.home() / ".cache" / APP))
AUDIO_DIR = CACHE_ROOT / "audio"
WAV_DIR = CACHE_ROOT / "wav16k"
RUNS_DIR = CACHE_ROOT / "runs"
MODELS_DIR = CACHE_ROOT / "models"
PROMPT_VERSION = "v2.7_review_fixed"

# ModelScope 与网络镜像配置
MODELSCOPE_HOST = "www.modelscope.cn"
MODELSCOPE_REPO_TMPL = "pengzhendong/faster-whisper-{size}"
MODELSCOPE_FILES = ("config.json", "tokenizer.json", "vocabulary.txt", "model.bin")
HF_MIRROR = "https://hf-mirror.com"
ALIDNS_IP = "223.5.5.5"

# 音频缓存的有效性下限。
MIN_AUDIO_BYTES = 100 * 1024

# 各尺寸模型最小合法二进制下限（防 1.1MB 残损模型中毒）
_MODEL_MIN_BYTES = {
    "tiny": 60 * 1024 * 1024,
    "base": 100 * 1024 * 1024,
    "small": 300 * 1024 * 1024,
    "medium": 1000 * 1024 * 1024,
    "distil-large": 1200 * 1024 * 1024,  # distil-large 权重大约 1.5GB
    "large": 2000 * 1024 * 1024,
}
MIN_MODEL_BIN_BYTES = 1024 * 1024


def min_bytes_for_model(model_name: str) -> int:
    name = model_name.lower()
    # 优先检测 distil 变体（如 distil-large, distil-whisper-large 等）
    if "distil" in name and "large" in name:
        return _MODEL_MIN_BYTES["distil-large"]
    # 从最长 key 开始匹配，防止 "large" 误匹配并抢占 "distil-large"
    for k in sorted(_MODEL_MIN_BYTES, key=len, reverse=True):
        if k == name or name.startswith(f"{k}.") or f"-{k}" in name or f"{k}-" in name or k in name:
            return _MODEL_MIN_BYTES[k]
    return MIN_MODEL_BIN_BYTES

BILIBILI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}

# 算法与技术专有名词偏置提示词（中英双语，涵盖通用计算机科学、体系结构、网络、系统与算法）
TECH_PROMPT = (
    "以下是普通话讲解内容，请使用规范简体中文并补充恰当标点符号。"
    "涉及计算机科学与工程术语：算法、数据结构、时间复杂度、空间复杂度、"
    "递归、迭代、动态规划、分治、贪心、树、图、堆、栈、队列、哈希表、"
    "CPU、内存、缓存、虚拟地址、进程、线程、协程、并发、锁、互斥、信号量、"
    "TCP、UDP、HTTP、Socket、客户端、服务端、状态机、一致性、分布式系统。"
)

TECH_PROMPT_EN = (
    "Computer science, engineering and programming lecture with technical terminology: "
    "algorithms, data structures, time complexity, space complexity, recursion, "
    "iteration, dynamic programming, binary search, tree traversal, graph theory, "
    "CPU, memory, cache, thread, concurrency, mutex, deadlock, TCP, UDP, socket, "
    "distributed systems, consensus, state machine, client, server."
)

_DLL_HANDLES = []


# ---------------------------------------------------------------- Windows CUDA 与环境自适应

def _add_nvidia_dll_dirs() -> list:
    """Windows 下将 pip 安装的 CUDA 运行库目录注册进 DLL 搜索路径与 PATH。"""
    global _DLL_HANDLES
    if os.name != "nt":
        return _DLL_HANDLES
    if _DLL_HANDLES:
        return _DLL_HANDLES
    try:
        search_roots = []
        try:
            search_roots.extend(site.getsitepackages())
        except Exception:
            pass
        try:
            search_roots.append(site.getusersitepackages())
        except Exception:
            pass

        bin_dirs = []
        for sp in search_roots:
            nvidia_root = Path(sp) / "nvidia"
            if not nvidia_root.is_dir():
                continue
            for bin_dir in nvidia_root.glob("*/bin"):
                bin_dirs.append(bin_dir)
                try:
                    _DLL_HANDLES.append(os.add_dll_directory(str(bin_dir)))
                except Exception:
                    pass

        if bin_dirs:
            existing = os.environ.get("PATH", "")
            new_dirs = [str(d) for d in bin_dirs if str(d) not in existing]
            if new_dirs:
                os.environ["PATH"] = os.pathsep.join(new_dirs + [existing])
    except Exception:
        pass
    return _DLL_HANDLES


def resolve_device(preference: str, compute_type_pref: str) -> tuple[str, str]:
    """智能解析运行设备与精度，杜绝 CPU 跑 float16 的崩溃。"""
    if preference == "cpu":
        ct = "int8" if compute_type_pref in ("default", "float16", "auto") else compute_type_pref
        return "cpu", ct
    if preference == "cuda":
        _add_nvidia_dll_dirs()
        ct = "float16" if compute_type_pref in ("default", "auto") else compute_type_pref
        return "cuda", ct

    # preference == "auto"
    _add_nvidia_dll_dirs()
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            ct = "float16" if compute_type_pref in ("default", "auto") else compute_type_pref
            return "cuda", ct
    except Exception:
        pass
    return "cpu", "int8"


def get_ffmpeg_exe() -> str:
    """自动定位 ffmpeg 可执行程序（优先系统 PATH，回退 imageio_ffmpeg）。"""
    f = shutil.which("ffmpeg")
    if f:
        return f
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    raise RuntimeError("未检测到 ffmpeg，请通过 'pip install imageio-ffmpeg' 或将 ffmpeg 安装至系统 PATH")


def get_audio_duration(path: Path) -> float:
    """获取音频时长（优先 Python 内置 wave 模块秒级读取，无需外部 ffprobe）。"""
    if path.suffix.lower() == ".wav":
        try:
            import wave
            with wave.open(str(path), 'rb') as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            pass

    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(path)],
                             check=True, capture_output=True, text=True).stdout.strip()
        return float(out)

    ffmpeg = get_ffmpeg_exe()
    proc = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True, errors="ignore")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if m:
        h, m_, s = m.groups()
        return int(h) * 3600 + int(m_) * 60 + float(s)
    raise RuntimeError(f"无法获取音频时长: {path}")


def fmt_ts(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def parse_ts(ts_str: str) -> float:
    """将 hh:mm:ss 或 mm:ss 字符串解析为浮点秒数。"""
    try:
        parts = [float(x) for x in ts_str.strip().split(":")]
        if len(parts) == 3:
            return parts[0] * 3600.0 + parts[1] * 60.0 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60.0 + parts[1]
        if len(parts) == 1:
            return parts[0]
    except Exception:
        pass
    return 0.0


def atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _audio_is_decodable(path: Path) -> bool:
    """快速探测音频文件是否可被解码，防止损坏文件锁死缓存。"""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            r = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=5
            )
            return r.returncode == 0 and "audio" in r.stdout
        except Exception:
            pass
    try:
        ffmpeg = get_ffmpeg_exe()
        r = subprocess.run(
            [ffmpeg, "-v", "error", "-ss", "0", "-t", "0.5", "-i", str(path), "-f", "null", "-"],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return True


def resolve_video_id(source: str, video_id: Optional[str] = None) -> str:
    """从源提取消毒后的 video_id，严格防止路径穿越。支持提取 B 站分P (?p=N, _pN)。"""
    if video_id:
        return re.sub(r"[^\w\-_]", "_", Path(video_id).name)
    m_bv = re.search(r"(BV[a-zA-Z0-9]+)", source)
    if m_bv:
        m_p = re.search(r"[?&]p=(\d+)|_(?:p|P)(\d+)", source)
        if m_p:
            p_num = m_p.group(1) or m_p.group(2)
            return f"{m_bv.group(1)}_p{p_num}"
        return m_bv.group(1)
    m_yt = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", source)
    if m_yt:
        return m_yt.group(1)
    clean = re.sub(r"[^\w\-_]", "_", source.split("?")[0].rstrip("/").split("/")[-1])
    return clean if clean else hashlib.md5(source.encode()).hexdigest()[:12]


# ---------------------------------------------------------------- ModelScope 国内源与代理穿透

def _resolve_real_ip(hostname: str) -> Optional[str]:
    """通过公共 DNS 获取真实 IP，绕开 Clash 等代理软件的 fake-IP 劫持。"""
    import requests
    import urllib3
    urllib3.disable_warnings()
    try:
        resp = requests.get(
            f"https://{ALIDNS_IP}/resolve",
            params={"name": hostname, "type": "A"},
            timeout=5, verify=False,
        )
        for a in resp.json().get("Answer", []):
            if a.get("type") == 1:
                return a.get("data")
    except Exception:
        pass
    return None


class _PinnedDNS:
    """临时将域名钉到指定 IP 的上下文管理器。"""
    def __init__(self, hostname: str, ip: str):
        self.hostname = hostname
        self.ip = ip
        self._original = None

    def __enter__(self):
        import socket
        self._original = socket.getaddrinfo

        def _pinned_gai(host, port, *args, **kwargs):
            if host == self.hostname:
                host = self.ip
            return self._original(host, port, *args, **kwargs)

        socket.getaddrinfo = _pinned_gai
        return self

    def __exit__(self, *args):
        import socket
        if self._original:
            socket.getaddrinfo = self._original


def _is_valid_model_dir(d: Path, model_name: str = "") -> bool:
    """判断模型目录是否真的可用。

    【为什么不能只看"文件存在且非空"】ModelScope 端点一旦写错，会把文件列表
    JSON 写进每个文件。这些文件"存在且非空"，于是被判为合法缓存永久复用，
    **坏了也永远不会重下**——这是个自我锁死的中毒循环。
    所以必须校验内容形态，而不是只看存在性：

      · model.bin 是二进制权重，开头不可能是 `{`
      · config.json 必须是能解析的 JSON
      · 权重体积必须过该模型的最低下限（tiny 60MB, medium 1000MB 等）
    """
    if not all((d / f).exists() for f in MODELSCOPE_FILES):
        return False
    try:
        model_bin = d / "model.bin"
        threshold = min_bytes_for_model(model_name) if model_name else MIN_MODEL_BIN_BYTES
        if model_bin.stat().st_size < threshold:
            return False
        with open(model_bin, "rb") as fh:
            head = fh.read(16)
        if head.startswith(b"{"):        # 权重是二进制，出现 { 说明下成了 JSON
            return False
        with open(d / "config.json", "r", encoding="utf-8") as fh:
            json.load(fh)
    except Exception:
        return False
    return True


def download_model_from_modelscope(model_size: str) -> Optional[Path]:
    """从阿里云魔搭下载模型（国内约 2-3 MB/s）。"""
    import requests
    dest = MODELS_DIR / f"faster-whisper-{model_size}"

    if _is_valid_model_dir(dest, model_size):
        print(f"[model] 本地已有可用模型：{dest.name}", file=sys.stderr)
        return dest

    # 目录存在但校验不过 → 整体清空重下。
    # 不能只靠下面逐文件的 "存在就跳过"：坏文件也"存在"，
    # 会被永久保留，形成坏了也永远不重下的中毒循环。
    if dest.exists():
        print(f"[model] 检测到模型目录无效，整体清除后重下：{dest.name}", file=sys.stderr)
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)

    repo = MODELSCOPE_REPO_TMPL.format(size=model_size)
    # 【端点别写错】必须是 /repo。/repo/files 是**列文件**接口，
    # 给它传 FilePath 只会返回文件列表 JSON，会被原样写进 model.bin 等文件里，
    # 造出一个"存在且非空"的损坏模型目录。实测对比：
    #   /repo/files?FilePath=config.json → {"Code":200,"Data":{"Files":[...   （列表）
    #   /repo?FilePath=config.json       → {"alignment_heads": [[13,15],...  （真内容）
    base_url = f"https://{MODELSCOPE_HOST}/api/v1/models/{repo}/repo"

    def _fetch(use_pinned_ip: bool) -> bool:
        ctx = _PinnedDNS(MODELSCOPE_HOST, _resolve_real_ip(MODELSCOPE_HOST)) if use_pinned_ip else None
        if ctx and not ctx.ip:
            return False
        try:
            if ctx:
                ctx.__enter__()
            for filename in MODELSCOPE_FILES:
                target = dest / filename
                if target.exists() and target.stat().st_size > 0:
                    continue
                resp = requests.get(
                    base_url,
                    params={"Revision": "master", "FilePath": filename},
                    stream=True, timeout=60,
                )
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                done = 0
                tmp = target.with_suffix(target.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(131072):
                        fh.write(chunk)
                        done += len(chunk)
                        if total > 1024 * 1024:
                            pct = done * 100 // total
                            print(f"\r[model] {filename} {pct}% ({done // 1048576}/{total // 1048576} MB)",
                                  end="", file=sys.stderr)
                if total > 1024 * 1024:
                    print("", file=sys.stderr)
                tmp.replace(target)
            return True
        except Exception as exc:
            print(f"[model] ModelScope 下载失败：{exc}", file=sys.stderr)
            return False
        finally:
            if ctx:
                ctx.__exit__(None, None, None)

    print(f"[model] 正在从 ModelScope 国内源拉取模型 {model_size}（仅首次需要）...", file=sys.stderr)
    if _fetch(use_pinned_ip=False):
        return dest
    if _fetch(use_pinned_ip=True):
        return dest
    return None


def load_whisper_model(model_name: str, device: str, compute_type: str, model_source: str = "auto"):
    """加载 Faster-Whisper 模型，支持本地缓存、ModelScope、官方 HF 与 HF 镜像精准路由。"""
    if device in ("cuda", "auto"):
        _add_nvidia_dll_dirs()

    # 1. 命中本地缓存（校验内容形态与体积，杜绝残存残包）
    local_model_dir = MODELS_DIR / f"faster-whisper-{model_name}"
    if _is_valid_model_dir(local_model_dir, model_name):
        print(f"[model] 命中本地离线缓存模型: {local_model_dir.name}", file=sys.stderr)
        model_ref = str(local_model_dir)
    elif model_source in ("auto", "modelscope"):
        ms_dest = download_model_from_modelscope(model_name)
        if ms_dest:
            model_ref = str(ms_dest)
        else:
            os.environ.setdefault("HF_ENDPOINT", HF_MIRROR)
            model_ref = model_name
    elif model_source == "mirror":
        os.environ.setdefault("HF_ENDPOINT", HF_MIRROR)
        model_ref = model_name
    elif model_source == "hf":
        # 官方 HF 直连：清除镜像环境变量
        os.environ.pop("HF_ENDPOINT", None)
        model_ref = model_name
    else:
        model_ref = model_name

    from faster_whisper import WhisperModel
    return WhisperModel(model_ref, device=device, compute_type=compute_type), model_ref


# ---------------------------------------------------------------- 字幕直达通道（恢复秒级抓取）

_ZH_MANUAL = ("zh-hans", "zh-cn", "zh", "zh-hant", "zh-tw")
_ZH_AUTO = ("ai-zh", "zh-auto")


def pick_subtitle(info: dict, prefer_lang: Optional[str] = None) -> Optional[tuple]:
    """从 info 提取字幕轨道。若指定 prefer_lang 优先匹配（中文默认简中优先），否则默认优先中文字幕。"""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    # 若显式指定了语言（非 auto/none）
    if prefer_lang and prefer_lang not in ("auto", "none"):
        pref = prefer_lang.lower()
        # 1. 精确匹配（人工轨道优先于自动轨道）
        for source, is_auto in ((manual, False), (auto, True)):
            for lang in source:
                if lang.lower() == pref:
                    return lang, source[lang], is_auto

        # 2. 如果目标是中文前缀，严格保持简体优先顺序，杜绝 dict 乱序命中 zh-Hant
        if pref.startswith("zh"):
            for key in _ZH_MANUAL:
                for lang in manual:
                    if lang.lower() == key:
                        return lang, manual[lang], False
            for key in _ZH_AUTO:
                for lang in auto:
                    if lang.lower() == key:
                        return lang, auto[lang], True
            for source, is_auto in ((manual, False), (auto, True)):
                for lang in source:
                    if "zh" in lang.lower():
                        return lang, source[lang], is_auto
        else:
            # 其他语言前缀匹配：按具体度（人工优先，再按标签长度降序）排序
            candidates = []
            for source, is_auto in ((manual, False), (auto, True)):
                for lang in source:
                    if lang.lower().startswith(pref):
                        candidates.append((lang, source[lang], is_auto))
            if candidates:
                # 排序规则：人工轨道(is_auto=False=0)优先于自动轨道(is_auto=True=1)，
                # 同类中标签越长越具体（如 en-US > en）优先。
                candidates.sort(key=lambda x: (x[2], -len(x[0])))
                return candidates[0]

    # 默认兜底：按简体中文优先匹配
    for key in _ZH_MANUAL:
        for lang in manual:
            if lang.lower() == key:
                return lang, manual[lang], False
    for key in _ZH_AUTO:
        for lang in auto:
            if lang.lower() == key:
                return lang, auto[lang], True
    for source, is_auto in ((manual, False), (auto, True)):
        for lang in source:
            if "zh" in lang.lower():
                return lang, source[lang], is_auto
    return None


def parse_subtitle(raw: str) -> Optional[str]:
    """解析 B站 JSON / SRT / VTT 字幕文本，支持 HTML 实体自动反转义。"""
    stripped = raw.lstrip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            body = data.get("body") or []
            lines = []
            for seg in body:
                content = html.unescape((seg.get("content") or "").strip())
                if content:
                    lines.append(f"[{fmt_ts(seg.get('from', 0))}] {content}")
            return "\n".join(lines) or None
        except Exception:
            return None

    lines = []
    pending_time = None
    for line in stripped.splitlines():
        line = line.rstrip()
        if not line:
            pending_time = None
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        # SRT 序号行：仅当处于新段落开头（pending_time 为 None）且为纯数字时跳过
        if pending_time is None and line.isdigit():
            continue
        m = re.match(r"(?:(\d{1,2}):)?(\d{2}:\d{2})[.,](\d{1,3})\s*-->", line)
        if m:
            h, ms = m.group(1), m.group(2)
            pending_time = f"{int(h):02d}:{ms}" if h else f"00:{ms}"
            continue
        clean = html.unescape(re.sub(r"<[^>]+>", "", line).strip())
        if clean:
            lines.append(f"[{pending_time}] {clean}" if pending_time else clean)
    return "\n".join(lines) or None


def fetch_subtitle_text(entry: list, platform: str) -> Optional[str]:
    import requests
    if not entry:
        return None
    candidates = sorted(entry, key=lambda e: 0 if e.get("ext") == "json" else 1)
    for item in candidates:
        url = item.get("url")
        if not url:
            continue
        try:
            headers = BILIBILI_HEADERS if platform == "bilibili" else {}
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            text = parse_subtitle(resp.text)
            if text:
                return text
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- 音频下载与切片缓存

def fetch_metadata(source: str, platform: str, video_id: str) -> dict:
    """快速探测并缓存视频元数据（零音频下载，仅抓取标题/时长/字幕轨道）。"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = AUDIO_DIR / f"{platform}_{video_id}.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if data.get("title") and ("subtitles" in data or "automatic_captions" in data):
                return data
        except Exception:
            pass

    local_src = Path(source)
    if local_src.is_file():
        # 本地音频/视频文件，直接通过本地探针提取元数据，不发起网络请求
        dur = 0.0
        try:
            dur = get_audio_duration(local_src)
        except Exception:
            pass
        meta = {
            "title": local_src.stem,
            "author": "Local",
            "duration": dur,
            "description": f"Local media file: {local_src.name}",
            "webpage_url": str(local_src.resolve()),
            "subtitles": {},
            "automatic_captions": {},
            "chapters": [],
            "source": source,
            "video_id": video_id,
        }
        atomic_write_json(meta_path, meta)
        return meta

    import yt_dlp
    url = source
    if platform == "bilibili" and not (source.startswith("http://") or source.startswith("https://")):
        m_part = re.match(r"^(BV[a-zA-Z0-9]+)[_?&](?:p|P)?(\d+)$", source)
        if m_part:
            url = f"https://www.bilibili.com/video/{m_part.group(1)}?p={m_part.group(2)}"
        else:
            url = f"https://www.bilibili.com/video/{source}"

    opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
    }
    if platform == "bilibili":
        opts["proxy"] = ""
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise RuntimeError(f"获取视频元数据为空: {source}")
    except Exception as exc:
        raise RuntimeError(f"获取视频元数据失败: {exc}") from None

    meta = {
        "title": info.get("title") or "",
        "author": info.get("uploader") or info.get("channel") or "",
        "duration": info.get("duration") or 0,
        "description": info.get("description") or "",
        "webpage_url": info.get("webpage_url") or url,
        "subtitles": info.get("subtitles"),
        "automatic_captions": info.get("automatic_captions"),
        "chapters": info.get("chapters") or [],
        "source": source,
        "video_id": video_id,
    }
    atomic_write_json(meta_path, meta)
    return meta


def download_audio(source: str, platform: str, dest: Path) -> dict:
    """按 ID 缓存音频，使用 yt-dlp 抓取 bestaudio 与元数据。"""
    import yt_dlp

    url = source
    if platform == "bilibili" and not (source.startswith("http://") or source.startswith("https://")):
        m_part = re.match(r"^(BV[a-zA-Z0-9]+)[_?&](?:p|P)?(\d+)$", source)
        if m_part:
            url = f"https://www.bilibili.com/video/{m_part.group(1)}?p={m_part.group(2)}"
        else:
            url = f"https://www.bilibili.com/video/{source}"

    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": str(dest.with_suffix(".%(ext)s")),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        "noplaylist": True,
        "postprocessors": [],
    }
    if platform == "bilibili":
        opts["proxy"] = ""

    dest.parent.mkdir(parents=True, exist_ok=True)

    # 【为什么进来先删残留】ensure_audio 只在校验不通过时才调用本函数，
    # 也就是说"缓存里那个文件是坏的"。但 yt-dlp 发现同名文件已存在会
    # **静默跳过下载**，于是坏文件被原样留下，又被下面的精确匹配捡回来
    # 当成"下载成功"返回 —— 校验层拒绝了它，下载层又把它交还，等于没校验。
    # 实测：预置 500 字节坏文件，download_audio 返回"成功"且文件仍是 500 字节，
    # 全链路跑完输出 0 字却报 [done]。所以必须先把残留清掉，逼 yt-dlp 真下载。
    for stale in dest.parent.glob(f"{dest.stem}.*"):
        if stale.is_file() and stale.suffix != ".json":
            stale.unlink(missing_ok=True)

    meta = {}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info:
            meta = {
                "title": info.get("title") or "",
                "author": info.get("uploader") or info.get("channel") or "",
                "duration": info.get("duration") or 0,
                "description": info.get("description") or "",
                "webpage_url": info.get("webpage_url") or url,
                "subtitles": info.get("subtitles"),
                "automatic_captions": info.get("automatic_captions"),
            }

    # 精确匹配文件名，杜绝前缀冲突
    exact_candidates = [
        p for p in dest.parent.iterdir()
        if p.is_file() and p.stem == dest.stem and not p.name.endswith(".part") and p.suffix != ".json"
    ]
    if not exact_candidates:
        raise RuntimeError(f"音频下载失败，未找到目标文件: {dest.name}")
    downloaded = max(exact_candidates, key=lambda p: p.stat().st_size)

    # 下载结果复查：这是最后一道闸。不复查的话，任何"下了一半"的产物
    # 都会进缓存，此后每次运行都基于残缺音频转录，产出空笔记却报成功。
    actual = downloaded.stat().st_size
    if actual < MIN_AUDIO_BYTES:
        downloaded.unlink(missing_ok=True)
        raise RuntimeError(
            f"音频下载结果异常：{downloaded.name} 仅 {actual} 字节"
            f"（下限 {MIN_AUDIO_BYTES}），判定失败并已清除")

    if downloaded != dest:
        if dest.exists():
            dest.unlink()
        downloaded.replace(dest)

    return meta


def ensure_audio(source: str, platform: str, video_id: str, existing_meta: Optional[dict] = None) -> tuple[Path, dict]:
    local_src = Path(source)
    if local_src.is_file():
        # 本地音频/视频文件，直接使用其本身转码或作为音频输入
        meta = existing_meta or {}
        if not meta:
            meta = fetch_metadata(source, platform, video_id)
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        meta_path = AUDIO_DIR / f"{platform}_{video_id}.json"
        meta.update({"source": source, "video_id": video_id, "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S")})
        atomic_write_json(meta_path, meta)
        return local_src, meta

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    m4a = AUDIO_DIR / f"{platform}_{video_id}.m4a"
    meta_path = m4a.with_suffix(".json")

    # 缓存检验：必须存在、大小达标、元数据完整，且必须通过可解码探针！
    # 阈值统一用 MIN_AUDIO_BYTES，与 download_audio 的复查口径一致。
    if m4a.exists() and m4a.stat().st_size >= MIN_AUDIO_BYTES and meta_path.exists():
        if _audio_is_decodable(m4a):
            print(f"[cache] 命中本地音频缓存: {m4a.name}（跳过网络下载）", file=sys.stderr)
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                return m4a, meta
            except Exception:
                pass
        else:
            print(f"[cache] ⚠️ 检测到本地音频文件损坏（无法解码），整体清除并重新下载: {m4a.name}", file=sys.stderr)
            m4a.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)

    print(f"[cache] 音频缓存未命中，启动下载音频流: {video_id}", file=sys.stderr)
    meta = download_audio(source, platform, m4a)
    if existing_meta:
        for k, v in existing_meta.items():
            if k not in meta or not meta[k]:
                meta[k] = v
    meta.update({"source": source, "video_id": video_id, "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    atomic_write_json(meta_path, meta)
    return m4a, meta


def ensure_wav16k(m4a: Path, video_id: str) -> Path:
    WAV_DIR.mkdir(parents=True, exist_ok=True)
    wav = WAV_DIR / f"{video_id}.wav"
    if wav.exists() and wav.stat().st_size > 100 * 1024:
        try:
            import wave
            with wave.open(str(wav), "rb") as w:
                _ = w.getnframes()
            print(f"[cache] 命中 16kHz WAV 缓存: {wav.name}", file=sys.stderr)
            return wav
        except Exception:
            print(f"[cache] ⚠️ 发现损坏的 WAV 缓存，清理并重新转码: {wav.name}", file=sys.stderr)
            wav.unlink(missing_ok=True)
    print("[cache] 转码 16kHz mono wav …", file=sys.stderr)
    ffmpeg = get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-y", "-i", str(m4a), "-ac", "1", "-ar", "16000", str(wav)],
                   check=True, capture_output=True)
    return wav


def plan_chunks(duration: float, chunk_len: float) -> list[dict]:
    chunks = []
    i = 0
    while i * chunk_len < duration:
        t0 = round(i * chunk_len, 3)
        t1 = round(min(duration, (i + 1) * chunk_len), 3)
        chunks.append({"id": i, "t0": t0, "t1": t1,
                       "status": "pending", "file": f"chunk_{i:04d}.json"})
        i += 1
    return chunks


def run_key(video_id: str, args) -> str:
    raw = "|".join([
        str(getattr(args, "platform", "bilibili")),
        video_id,
        str(args.model),
        str(getattr(args, "model_source", "auto")),
        str(args.language),
        f"vad={args.vad}",
        f"chunk={args.chunk_len}",
        f"beam={args.beam_size}",
        f"dev={args.device}",
        f"ct={args.compute_type}",
        f"dp={getattr(args, 'domain_prompt', None)}",
        PROMPT_VERSION,
    ])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def slice_wav(wav: Path, t0: float, t1: float, dest: Path) -> None:
    ffmpeg = get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-y", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
                    "-i", str(wav), "-ac", "1", "-ar", "16000", str(dest)],
                   check=True, capture_output=True)


_CUDA_MSG_PATTERN = re.compile(
    r"(cuda (?:error|failed|out of memory|runtime)|"
    r"cuda_error|out of memory|outofmemory|"
    r"cublas|cudnn|alloc_failed|device-side|no kernel image|driver error)",
    re.IGNORECASE,
)


def _is_oom_or_cuda(exc: BaseException) -> bool:
    """精准且鲁棒地判定异常是否由 CUDA 驱动、显存 OOM 或 ctranslate2/cublas 崩溃引起，避免裸 'cuda' 路径假阳性。"""
    try:
        import torch
        if isinstance(exc, torch.cuda.OutOfMemoryError):
            return True
    except Exception:
        pass
    msg = str(exc)
    return bool(_CUDA_MSG_PATTERN.search(msg))


def detect_language(model, model_ref: str, wav: Path, run_dir: Path, vad: bool = True,
                    duration: float = 0.0) -> tuple[str, any]:
    """前 30s 裸探测语言（不注入特定语言提示词，避免对英文/非中文产生偏置），尊重用户 vad 设置。
    若首次探测置信度 < 0.6（常见于 B 站讲课视频有 30s 静音片头），自动从视频 1/4 处重试一次。
    """
    def _probe_at(t0: float) -> tuple[str, any, float]:
        """在 t0 处截 30s 探测，返回 (language, model, probability)。"""
        nonlocal model
        probe = run_dir / "_probe.wav"
        slice_wav(wav, t0, t0 + 30.0, probe)
        try:
            _, info = model.transcribe(str(probe), language=None, vad_filter=vad)
        except Exception as exc:
            if _is_oom_or_cuda(exc):
                print(f"[model] ⚠️ 语言探测触发 CUDA 错误，回退至 CPU int8...", file=sys.stderr)
                from faster_whisper import WhisperModel
                model = WhisperModel(model_ref, device="cpu", compute_type="int8")
                _, info = model.transcribe(str(probe), language=None, vad_filter=vad)
            else:
                raise
        finally:
            probe.unlink(missing_ok=True)
        return info.language, model, info.language_probability

    lang, model, prob = _probe_at(0.0)
    print(f"[lang] 检测语言: {lang} (置信度 {prob:.2f})", file=sys.stderr)

    # 首次置信度偏低且视频时长足够 → 跳过静音片头，在 1/4 处重试
    if prob < 0.6 and duration > 120.0:
        retry_t0 = max(30.0, duration / 4)
        print(f"[lang] ⚠️ 置信度偏低，在 {retry_t0:.0f}s 处重试...", file=sys.stderr)
        lang2, model, prob2 = _probe_at(retry_t0)
        print(f"[lang] 重试结果: {lang2} (置信度 {prob2:.2f})", file=sys.stderr)
        if prob2 > prob:
            lang, prob = lang2, prob2

    if prob < 0.6:
        print(f"[lang] ⚠️ 语言置信度仍偏低，若转录异常可用 --language 显式指定", file=sys.stderr)
    return lang, model


def transcribe_chunk(model, model_ref: str, wav: Path, c: dict, args, language: str, run_dir: Path) -> tuple[list[dict], any]:
    """转录单块，修复中点裁剪、显存 OOM 与推理层 GPU->CPU 回退。"""
    t0, t1 = c["t0"], c["t1"]
    ext0, ext1 = max(0.0, t0 - 0.5), t1 + 0.5
    slice_len = ext1 - ext0
    tmp = run_dir / f"_tmp_{os.getpid()}.wav"
    slice_wav(wav, ext0, ext1, tmp)
    pbar = tqdm(total=slice_len, desc=f"  chunk {c['id']:04d}", unit="s", leave=False,
                bar_format="{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]")
    segs, last = [], 0.0

    # 精准语言前缀匹配：中文与英文各自分配专属技术提示词，并附加用户自定义 --domain-prompt
    if language and language.startswith("zh"):
        base_prompt = TECH_PROMPT
    elif language and language.startswith("en"):
        base_prompt = TECH_PROMPT_EN
    else:
        base_prompt = ""

    domain_p = getattr(args, "domain_prompt", None) or ""
    if base_prompt and domain_p:
        prompt = f"{base_prompt} 领域术语补充：{domain_p}"
    elif domain_p:
        prompt = domain_p
    elif base_prompt:
        prompt = base_prompt
    else:
        prompt = None

    def _execute(m):
        nonlocal last
        segments, _ = m.transcribe(
            str(tmp),
            language=language,
            vad_filter=args.vad,
            vad_parameters=dict(threshold=0.5, min_silence_duration_ms=500, speech_pad_ms=400),
            beam_size=args.beam_size,
            condition_on_previous_text=False,
            initial_prompt=prompt,
        )
        for seg in segments:
            advance = max(0.0, min(slice_len, seg.end - last))
            pbar.update(advance)
            last = seg.end
            start, end = seg.start + ext0, seg.end + ext0

            # 中点归属原则，杜绝跨边界丢句
            mid = (start + end) / 2.0
            if mid < t0 or mid >= t1:
                continue

            segs.append({"start": round(max(t0, start), 3),
                         "end": round(min(t1, end), 3),
                         "text": seg.text.strip()})
        pbar.update(max(0.0, slice_len - pbar.n))

    try:
        try:
            _execute(model)
        except Exception as exc:
            if _is_oom_or_cuda(exc):
                print(f"\n[model] ⚠️ 推理期捕获显存/CUDA错误 ({exc})，自动清理显存并无缝回退至 CPU int8 继续当前块...", file=sys.stderr)
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                from faster_whisper import WhisperModel
                model = WhisperModel(model_ref, device="cpu", compute_type="int8")
                segs.clear()
                last = 0.0
                pbar.n = 0
                _execute(model)
            else:
                raise
    finally:
        pbar.close()
        tmp.unlink(missing_ok=True)
    return segs, model


def transcribed_chunk_ids(run_dir: Path, manifest: dict) -> list[int]:
    """列出磁盘上**真正存在分块文件**的 chunk id（保持 manifest 顺序）。

    【为什么需要这个函数】--chunks 模式只转录用户选中的那几块，其余分块在
    manifest 里一直是 pending、磁盘上没有文件。而全量归档那一行原本写死
    selected_chunk_ids=None（=要求合并全部分块），于是 merge() 的完整性闸门
    当场抛 "分块文件缺失" —— 用户等了几十分钟转录完，最后一步 0 产出。
    merge() 的严格性本身是对的（不能让残缺数据冒充完整笔记），
    所以这里不改 merge，而是让归档路径只声明"我确实有的那些块"。
    """
    return [c["id"] for c in manifest["chunks"] if (run_dir / c["file"]).exists()]


def merge(run_dir: Path, manifest: dict, selected_chunk_ids: Optional[list[int]] = None) -> list[dict]:
    segs = []
    chunks = manifest["chunks"]
    if selected_chunk_ids is not None:
        chunks = [c for c in chunks if c["id"] in selected_chunk_ids]
    for c in chunks:
        cf = run_dir / c["file"]
        if not cf.exists():
            raise RuntimeError(f"合并失败：分块文件缺失 {cf.name}（分块状态为 {c.get('status')}），数据不完整拒绝产出残缺笔记")
        segs.extend(json.loads(cf.read_text(encoding="utf-8"))["segments"])
    segs.sort(key=lambda s: s["start"])

    # 音频分块边界时间戳区间去重：
    # 针对音频路径 0.5s ext 重叠区在边界处引发的整句重复（15~40字）。
    # 若当前 seg 与前一个 seg 时间重叠超过较短者时长的 70%，且文本包含或高度重合，保留更完整/较长的一句。
    out = []
    for s in segs:
        if out:
            prev = out[-1]
            overlap = min(prev["end"], s["end"]) - max(prev["start"], s["start"])
            if overlap > 0:
                shorter = min(prev["end"] - prev["start"], s["end"] - s["start"])
                if shorter > 0 and (overlap / shorter) > 0.7:
                    p_text = prev.get("text", "").strip()
                    s_text = s.get("text", "").strip()
                    if p_text in s_text or s_text in p_text or len(s_text) > len(p_text):
                        out[-1] = s
                    continue
        out.append(s)
    return out


# ---------------------------------------------------------------- P1 智能脱水与切片检索支持

_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")

CHAT_NOISE_PATTERNS = [
    re.compile(p) for p in [
        r"^.*(扣[1一]|点个赞|投个币|粉丝牌|关注主播|谢谢.*礼物|送出.*飞机|送的.*礼物|感谢.*送的).*",
        r"^.*(声音没问题吧|录像还在|麦克风|卡了没|画面卡不卡|能听到吗|听得清吗).*",
        r"^.*(我喝口水|有点感冒|头晕|吃个饭|嗓子疼|先去个洗手间|抽根烟|开个空调|状态不好).*",
        r"^.*(换个编辑器|调下字体|开不开弹幕|看下评论区|看下群|私信我|走神了).*",
    ]
]

# 词界安全检测，防止 little / away 等误命中
TRAP_KEYWORDS_CN = ("坑", "错", "不对", "注意", "但是", "其实", "不过", "然而", "越界", "溢出", "死循环", "超时", "段错误", "为什么", "别", "小心", "容易犯", "反例")
TRAP_PATTERN_EN = re.compile(r"\b(bug|tle|mle|wa|error|fail|overflow)\b", re.IGNORECASE)

TECH_KEYWORDS_CN = ("递归", "递推", "状态", "转移", "边界", "复杂度", "空间", "时间", "数组", "指针", "背包", "贪心", "优化", "容量", "价值", "重量", "体积", "下标", "输入", "输出", "例题", "反例", "证明", "循环", "函数", "变量", "参数", "树", "图", "栈", "队列", "堆", "哈希", "排序", "二分", "分治", "剪枝", "记忆化", "滚动", "正序", "逆序", "倒序", "不变量")
TECH_PATTERN_EN = re.compile(r"\b(dp|dfs|bfs|max|min|vector|int|void|return|if|for|while|const|auto|struct|class|memo)\b", re.IGNORECASE)

CODE_INDICATOR_PATTERN = re.compile(
    r"([a-zA-Z_]\w*\s*[\(=\[<>]|->|\+\+|--|==|!=|<=|>=|;\s*$|[a-zA-Z_]\w*\[|\b(int|void|vector|for|while|if|return|dp|dfs|bfs|max|min|memo|f|g)\b)"
)


def parse_chunk_ids(chunks_str: Optional[str]) -> Optional[list[int]]:
    """解析分块列表字符串，支持逗号分隔与区间（如 '0,1,3' 或 '0-3'），兼容逆序与异常输入。"""
    if not chunks_str:
        return None
    ids = set()
    for part in chunks_str.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                s_val = int(start_s.strip())
                e_val = int(end_s.strip())
                low = min(s_val, e_val)
                high = max(s_val, e_val)
                if low >= 0:
                    ids.update(range(low, high + 1))
            else:
                val = int(part)
                if val >= 0:
                    ids.add(val)
        except ValueError:
            print(f"[warning] 忽略无法解析的分块序号: {part}", file=sys.stderr)
    return sorted(list(ids))


def analyze_text_signals(text: str, fallback_hints: Optional[list[str]] = None) -> dict:
    """提取文本中的深度教学特征：关键词、主题提示、技术密度、代码/公式/陷阱标记。"""
    if not text:
        return {
            "keywords": [],
            "topic_hints": fallback_hints or [],
            "density": 0.0,
            "has_code": False,
            "has_formula": False,
            "has_warning": False,
        }
    kw_hits = [k for k in TECH_KEYWORDS_CN if k in text]
    for m in TECH_PATTERN_EN.finditer(text):
        kw_hits.append(m.group(0).lower())

    unique_kws = list(dict.fromkeys(kw_hits))
    has_warning = any(w in text for w in TRAP_KEYWORDS_CN) or bool(TRAP_PATTERN_EN.search(text))
    has_code = bool(CODE_INDICATOR_PATTERN.search(text))
    has_formula = bool(re.search(r"(=|\+|-|\*|/|\^|dp\[|f\(|O\(|\\sum|\\le|\\ge|\\in|==|!=)", text))
    density = round(min(1.0, len(kw_hits) / max(1.0, len(text) / 80.0)), 2)

    hints = list(fallback_hints or [])
    if not hints and unique_kws:
        hints = unique_kws[:3]

    return {
        "keywords": unique_kws[:5],
        "topic_hints": hints,
        "density": density,
        "has_code": has_code,
        "has_formula": has_formula,
        "has_warning": has_warning,
    }


def extract_chapters_from_meta(meta: dict) -> list[dict]:
    """提取视频内嵌章节或简介中的时间轴目录，作为高价值免费 L0-A 导航信息。"""
    chapters = []
    raw_chapters = meta.get("chapters")
    if raw_chapters:
        for ch in raw_chapters:
            start = float(ch.get("start_time", 0.0))
            end = float(ch.get("end_time", 0.0))
            title = ch.get("title", "").strip()
            if title:
                chapters.append({"start": start, "end": end, "title": title})
        if chapters:
            return chapters

    desc = meta.get("description") or ""
    pattern = re.compile(r"(?:^|\n)\s*(?:\[|\()?((?:\d{1,2}:)?\d{2}:\d{2})(?:\]|\))?\s*[-—:]?\s*([^\n\r]+)")
    matches = pattern.findall(desc)
    for ts_str, title_str in matches:
        sec = parse_ts(ts_str)
        clean_title = title_str.strip()[:50]
        if clean_title and not clean_title.startswith("http"):
            chapters.append({"start": sec, "end": 0.0, "title": clean_title})

    for i in range(len(chapters) - 1):
        chapters[i]["end"] = chapters[i + 1]["start"]
    if chapters and meta.get("duration"):
        chapters[-1]["end"] = float(meta["duration"])
    return chapters


def generate_chunk_index(run_dir: Path, manifest: dict, chapters: Optional[list[dict]] = None) -> list[dict]:
    """生成 L0 级轻量分块导航目录，包含关键词、主题提示与技术密度特征。"""
    chunk_index = []
    for c in manifest["chunks"]:
        cf = run_dir / c["file"]
        full_chunk_text = ""
        status = c.get("status", "unknown")
        chars = 0
        if cf.exists():
            try:
                data = json.loads(cf.read_text(encoding="utf-8"))
                chunk_segs = data.get("segments", [])
                full_chunk_text = "".join(s.get("text", "") for s in chunk_segs)
                chars = len(full_chunk_text)
                status = "ready"
            except Exception:
                pass
        matching_chapters = [ch["title"] for ch in (chapters or []) if ch["start"] < c["t1"] and ch["end"] > c["t0"]]
        signals = analyze_text_signals(full_chunk_text, fallback_hints=matching_chapters)
        chunk_index.append({
            "id": c["id"],
            "start": fmt_ts(c["t0"]),
            "end": fmt_ts(c["t1"]),
            "duration_s": round(c["t1"] - c["t0"], 1),
            "status": status,
            "chars": chars,
            "keywords": signals["keywords"],
            "topic_hints": signals["topic_hints"],
            "density": signals["density"],
            "has_code": signals["has_code"],
            "has_formula": signals["has_formula"],
            "has_warning": signals["has_warning"],
        })
    return chunk_index


def generate_chunk_index_from_segments(segs: list[dict], duration: float, chunk_len: float,
                                       chapters: Optional[list[dict]] = None) -> list[dict]:
    """为字幕等即时段落生成包含技术特征的高清 L0 导航目录。"""
    chunks = plan_chunks(duration, chunk_len)
    chunk_index = []
    for c in chunks:
        t0, t1 = c["t0"], c["t1"]
        c_segs = [s for s in segs if t0 <= s.get("start", 0.0) < t1]
        text = "".join(s.get("text", "") for s in c_segs)
        matching_chapters = [ch["title"] for ch in (chapters or []) if ch["start"] < t1 and ch["end"] > t0]
        signals = analyze_text_signals(text, fallback_hints=matching_chapters)
        chunk_index.append({
            "id": c["id"],
            "start": fmt_ts(t0),
            "end": fmt_ts(t1),
            "duration_s": round(t1 - t0, 1),
            "status": "ready",
            "chars": len(text),
            "keywords": signals["keywords"],
            "topic_hints": signals["topic_hints"],
            "density": signals["density"],
            "has_code": signals["has_code"],
            "has_formula": signals["has_formula"],
            "has_warning": signals["has_warning"],
        })
    return chunk_index


def generate_chunk_index_from_chapters(chapters: list[dict], duration: float, chunk_len: float) -> list[dict]:
    """根据视频内嵌章节或时间轴目录构建 L0-A 免费导航索引。"""
    chunks = plan_chunks(duration, chunk_len)
    chunk_index = []
    for c in chunks:
        t0, t1 = c["t0"], c["t1"]
        matching_chapters = [ch["title"] for ch in chapters if ch["start"] < t1 and ch["end"] > t0]
        ch_text = " ".join(matching_chapters)
        signals = analyze_text_signals(ch_text, fallback_hints=matching_chapters)
        chunk_index.append({
            "id": c["id"],
            "start": fmt_ts(t0),
            "end": fmt_ts(t1),
            "duration_s": round(t1 - t0, 1),
            "status": "meta_indexed",
            "chars": len(ch_text),
            "keywords": signals["keywords"],
            "topic_hints": signals["topic_hints"],
            "density": signals["density"],
            "has_code": signals["has_code"],
            "has_formula": signals["has_formula"],
            "has_warning": signals["has_warning"],
        })
    return chunk_index


def scout_audio_chunks(source: str, platform: str, video_id: str, meta: dict,
                       chunks: list[dict], run_dir: Path, args) -> list[dict]:
    """L0-B 低成本粗侦察：每分块仅采样 20s 音频，用 tiny 模型极速粗转录，建立精准技术指纹导航。"""
    run_dir.mkdir(parents=True, exist_ok=True)
    scouts_cache_file = run_dir / "scouts.json"
    if scouts_cache_file.exists():
        try:
            return json.loads(scouts_cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    print("[scout] ⚡ 视频无字幕且无内嵌章节，启动 L0-B 快速侦察 (各切片仅采样 20s 音频)...", file=sys.stderr)
    m4a, meta = ensure_audio(source, platform, video_id, existing_meta=meta)
    wav = ensure_wav16k(m4a, video_id)

    device, compute_type = resolve_device(args.device, "int8" if args.device == "cpu" else "default")
    model, _ = load_whisper_model("tiny", device=device, compute_type=compute_type, model_source=args.model_source)

    scout_results = []
    for c in chunks:
        t0, t1 = c["t0"], c["t1"]
        sample_start = min(t0 + 20.0, max(t0, t1 - 25.0))
        sample_end = min(t1, sample_start + 20.0)
        if sample_end <= sample_start:
            sample_start, sample_end = t0, min(t1, t0 + 20.0)

        probe_wav = run_dir / f"_scout_{c['id']}.wav"
        probe_text = ""
        try:
            slice_wav(wav, sample_start, sample_end, probe_wav)
            lang_param = args.language if args.language not in ("auto", "none") else None
            segs, _ = model.transcribe(str(probe_wav), language=lang_param, vad_filter=True, beam_size=1)
            probe_text = "".join(s.text for s in segs).strip()
        except Exception as exc:
            print(f"[scout warning] chunk {c['id']}: {exc}", file=sys.stderr)
            probe_text = ""
        finally:
            probe_wav.unlink(missing_ok=True)

        signals = analyze_text_signals(probe_text)
        scout_results.append({
            "id": c["id"],
            "start": fmt_ts(t0),
            "end": fmt_ts(t1),
            "duration_s": round(t1 - t0, 1),
            "status": "scouted",
            "chars": len(probe_text),
            "keywords": signals["keywords"],
            "topic_hints": signals["topic_hints"],
            "density": signals["density"],
            "has_code": signals["has_code"],
            "has_formula": signals["has_formula"],
            "has_warning": signals["has_warning"],
        })

    atomic_write_json(scouts_cache_file, scout_results)
    print(f"[scout] ⚡ L0-B 侦察完成：已为 {len(scout_results)} 个分块建立技术指纹导航", file=sys.stderr)
    return scout_results


def extract_evidence(dehydrated_text: str, traps_raw: list[dict]) -> tuple[str, dict]:
    """L1.5 证据级压缩：从脱水正文中仅过滤保留关键定理、定义、公式、代码行与陷阱句。"""
    if not dehydrated_text:
        return "", {"evidence_chars": 0, "evidence_reduction": "0%"}

    lines = dehydrated_text.splitlines()
    evidence_lines = []
    traps_texts = {t.get("text", "").strip() for t in traps_raw if t.get("text")}

    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
        if line_s.startswith("[") and ("闲聊" in line_s or "已自动折叠" in line_s):
            continue

        clean_content = re.sub(r"^\[\d{1,3}:\d{2}(?::\d{2})?\]\s*", "", line_s).strip()

        has_tech = any(k in line_s for k in TECH_KEYWORDS_CN) or bool(TECH_PATTERN_EN.search(line_s))
        has_code = bool(CODE_INDICATOR_PATTERN.search(line_s))
        has_formula = bool(re.search(r"(=|\+|-|\*|/|\^|dp\[|f\(|O\(|\\sum|\\le|\\ge|\\in|==|!=)", line_s))
        has_trap = (any(w in line_s for w in TRAP_KEYWORDS_CN) or
                    bool(TRAP_PATTERN_EN.search(line_s)) or
                    clean_content in traps_texts or
                    any(clean_content and clean_content in tt for tt in traps_texts))

        if has_tech or has_code or has_formula or has_trap:
            evidence_lines.append(line_s)

    evidence_text = "\n".join(evidence_lines)
    orig_chars = len(strip_timestamps(dehydrated_text).replace("\n", ""))
    ev_chars = len(strip_timestamps(evidence_text).replace("\n", ""))
    ev_ratio = f"{max(0.0, (1 - ev_chars / max(orig_chars, 1)) * 100):.1f}%"

    return evidence_text, {
        "evidence_chars": ev_chars,
        "evidence_reduction": ev_ratio,
    }


def dedup_consecutive(segs: list[dict], window: Optional[int] = None) -> list[dict]:
    """对连续分段消除尾首重叠复读（自适应中英文字符集密度：中文 window=8，英文放宽至 24）。"""
    out = []
    for s in segs:
        text = s.get("text", "").strip()
        if not text:
            continue
        if out:
            prev = out[-1]["text"]
            w = window if window is not None else (
                8 if _CJK_PATTERN.search(prev) else 24
            )
            for n in range(min(w, len(prev), len(text)), 2, -1):
                if prev[-n:] == text[:n]:
                    text = text[n:].strip()
                    break
        if text:
            s_copy = dict(s)
            s_copy["text"] = text
            out.append(s_copy)
    return out


def dehydrate_segments(segs: list[dict], is_subtitle: bool = False) -> tuple[str, list[dict], dict]:
    """对分段执行句子级脱水与无教学内容区间折叠。

    脱水机制：
      1. 单句过滤：依 CHAT_NOISE_PATTERNS 剔除纯寒暄口水句；
      2. 信号标记：has_tech / has_trap 仅用于区间折叠判断（当连续若干句既无代码/技术词也无陷阱警示时，折叠为闲聊标签）；
      3. 去重控制：is_subtitle=True 时对字幕路径执行 dedup_consecutive 消除 AI/自动字幕滑动窗口字级复读；
         音频分块已在 merge() 阶段通过时间戳重叠区间去重，无需且不应执行字级裁剪。
    """
    if not segs:
        return "", [], {
            "raw_chars": 0,
            "dedup_chars": 0,
            "dedup_removed": 0,
            "clean_chars": 0,
            "compression_ratio": "0%",
            "traps_count": 0,
        }

    # 1. 真实原始字数统计（去重前），作为压缩率唯一基准分母
    raw_char_count = sum(len(s.get("text", "").strip()) for s in segs)

    # 2. 仅对字幕路径执行滑动窗口去重（针对 AI 字幕尾首 4~8 字重叠）
    if is_subtitle:
        segs = dedup_consecutive(segs)
    dedup_char_count = sum(len(s.get("text", "").strip()) for s in segs)
    dedup_removed = raw_char_count - dedup_char_count

    parsed_lines = []
    for s in segs:
        body = s["text"].strip()
        sec = s["start"]
        time_str = fmt_ts(sec)
        parsed_lines.append({"time_str": time_str, "sec": sec, "text": body})

    processed_lines = []
    traps_raw = []

    for item in parsed_lines:
        body = item["text"]
        time_str = item["time_str"]
        sec = item["sec"]

        sub_sentences = re.split(r"([，。！？；…\n]+)", body)
        clean_sub = []
        has_any_tech = False
        has_any_trap = False

        paired_sentences = []
        i = 0
        while i < len(sub_sentences):
            text_part = sub_sentences[i]
            punct = sub_sentences[i + 1] if i + 1 < len(sub_sentences) else ""
            if text_part.strip():
                paired_sentences.append(text_part.strip() + punct)
            i += 2

        for s in paired_sentences:
            s_clean = s.strip()
            if not s_clean:
                continue

            s_clean = re.sub(r"(对吧|就是|然后|那个|怎么说|听懂了吗|也就是说|好吧|其实就是){2,}", r"\1", s_clean)
            s_clean = re.sub(r"([，。！？；]){2,}", r"\1", s_clean)

            has_code = bool(CODE_INDICATOR_PATTERN.search(s_clean))
            has_trap = any(k in s_clean for k in TRAP_KEYWORDS_CN) or bool(TRAP_PATTERN_EN.search(s_clean))
            # has_code 与技术词共同汇入 has_tech，用于保护包含代码的语句不被当作闲聊折叠
            has_tech = has_code or any(k in s_clean for k in TECH_KEYWORDS_CN) or bool(TECH_PATTERN_EN.search(s_clean))

            if has_trap:
                has_any_trap = True
                traps_raw.append({"time": time_str, "sec": sec, "text": s_clean})

            if has_tech:
                has_any_tech = True

            if not has_code and not has_trap:
                if any(p.match(s_clean) for p in CHAT_NOISE_PATTERNS):
                    continue

            clean_sub.append(s_clean)

        new_text = "".join(clean_sub).strip()
        if new_text:
            processed_lines.append({
                "time_str": time_str,
                "sec": sec,
                "text": new_text,
                "has_tech": has_any_tech,
                "has_trap": has_any_trap,
            })

    final_output_lines = []
    i = 0
    n = len(processed_lines)

    while i < n:
        cur = processed_lines[i]
        if not cur["has_tech"] and not cur["has_trap"]:
            start_idx = i
            start_sec = cur["sec"]
            start_time_str = cur["time_str"]

            while i < n and not processed_lines[i]["has_tech"] and not processed_lines[i]["has_trap"]:
                i += 1

            span_sec = processed_lines[i - 1]["sec"] - start_sec
            count_lines = i - start_idx

            if span_sec >= 90 and count_lines >= 3:
                end_time_str = processed_lines[i - 1]["time_str"]
                fold_tag = f"[{start_time_str} - {end_time_str} 闲聊互动/休息闲谈，已自动折叠]"
                final_output_lines.append(fold_tag)
            else:
                for k in range(start_idx, i):
                    item = processed_lines[k]
                    final_output_lines.append(f"[{item['time_str']}] {item['text']}")
        else:
            final_output_lines.append(f"[{cur['time_str']}] {cur['text']}")
            i += 1

    dehydrated_text = "\n".join(final_output_lines)
    # 口径一致性：纯文本比对统计压缩率，以最原始转录字数 raw_char_count 为基准分母
    plain_only = strip_timestamps(dehydrated_text)
    clean_chars = len(plain_only.replace("\n", ""))
    ratio = f"{max(0.0, (1 - clean_chars / max(raw_char_count, 1)) * 100):.1f}%"

    stats = {
        "raw_chars": raw_char_count,
        "dedup_chars": dedup_char_count,
        "dedup_removed": dedup_removed,
        "clean_chars": clean_chars,
        "compression_ratio": ratio,
        "traps_count": len(traps_raw),
    }

    return dehydrated_text, traps_raw, stats


def strip_timestamps(text: str) -> str:
    """彻底清除所有时间戳与折叠标记，输出纯粹正文。支持行内多标签与连续标记。"""
    if not text:
        return ""
    out = []
    # 去掉 ^ 锚点，允许行内出现多个时间戳标签时全部剥离
    pattern = re.compile(r"\[\d{1,2}:\d{2}(?::\d{2})?(?:\s*-\s*\d{1,2}:\d{2}(?::\d{2})?)?(?:\s+[^\]]*)?\]\s*")
    for line in text.split("\n"):
        clean = pattern.sub("", line).strip()
        if clean:
            out.append(clean)
    return "\n".join(out)


# ---------------------------------------------------------------- 主流程

def _output_chunk_index(chunk_index_payload: dict, args, video_id: str) -> int:
    prefix = Path(args.out) if args.out else RUNS_DIR / run_key(video_id, args) / "chunk_index"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = prefix if (args.out and Path(args.out).suffix == ".json") else prefix.with_suffix(".json")
    atomic_write_json(json_path, chunk_index_payload)
    if args.json or not args.out:
        print(json.dumps(chunk_index_payload, ensure_ascii=False, indent=2))
    print(f"[done] L0 分块索引已生成: {json_path}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="video2obsidian 提取与脱水引擎（v3.0 架构加固版）")
    ap.add_argument("source", help="视频 URL 或 ID")
    ap.add_argument("--mode", choices=["auto", "subtitle", "audio"], default="auto",
                    help="auto=优先字幕没有才转录（默认）/ subtitle=只要字幕 / audio=强制转录")
    ap.add_argument("--platform", default="bilibili")
    ap.add_argument("--video-id", default=None)
    ap.add_argument("--model", default="medium", help="whisper 模型，默认 medium")
    ap.add_argument("--model-source", choices=["auto", "modelscope", "hf", "mirror"], default="auto",
                    help="模型下载源：auto=本地缓存/ModelScope国内源优先（默认）")
    ap.add_argument("--language", default="auto", help="auto / zh / en / ja …")
    ap.add_argument("--domain-prompt", "--initial-prompt", dest="domain_prompt", default=None,
                    help="自定义转录提示词/专业术语偏置（将附加到内置技术提示词后，引导 Whisper 正确识别冷门领域术语）")
    ap.add_argument("--chunk-len", type=float, default=600.0)
    ap.add_argument("--chunks", default=None, help="仅提取/脱水指定分块，逗号分隔或区间（如 '0,1,3' 或 '0-3'）")
    ap.add_argument("--chunk-index", action="store_true", help="仅生成并输出分块 L0 导航索引 JSON（不返回全片正文）")
    ap.add_argument("--evidence", action="store_true", help="启用 L1.5 证据提炼模式：仅提取关键定理、公式、代码、陷阱句，二次压缩 40%%-60%% 上下文")
    ap.add_argument("--scout", action=argparse.BooleanOptionalAction, default=True, help="无字幕/章节时是否自动启动 L0-B 粗侦察（默认开启）")
    ap.add_argument("--full-archive", action="store_true", help="在 LLM 结果中也包含完整 content (原始字幕/转录) 和 content_plain（默认仅保存在本地 _archive.json）")
    ap.add_argument("--vad", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--device", default="auto", help="cuda / cpu")
    ap.add_argument("--compute-type", default="default", help="精度：float16 / int8 / default")
    ap.add_argument("--beam-size", type=int, default=5)
    ap.add_argument("--out", "-o", "--output", dest="out", default=None, help="输出文件路径或前缀")
    ap.add_argument("--json", action="store_true", help="以完整统一 JSON 格式输出到 stdout / 文件")
    ap.add_argument("--force", action="store_true", help="忽略分块断点，强制从头重转（保留音频缓存）")
    ap.add_argument("--force-download", action="store_true", help="强制清除音频与元数据缓存并重新下载")
    ap.add_argument("--force-all", action="store_true", help="全部重来（强制重下音频并从头重转）")
    args = ap.parse_args()

    if args.force_all:
        args.force = True
        args.force_download = True

    if args.chunk_len < 30.0:
        print("[error] --chunk-len 必须 >= 30 秒，拒绝执行", file=sys.stderr)
        return 2
    if args.beam_size < 1:
        print("[error] --beam-size 必须 >= 1，拒绝执行", file=sys.stderr)
        return 2
    if args.out:
        out_p = Path(args.out)
        if out_p.is_dir() or str(args.out).endswith(("/", "\\")):
            print("[error] --out 指向目录，请传具体文件路径或名称前缀（如 -o ./out/note）", file=sys.stderr)
            return 2

    video_id = resolve_video_id(args.source, args.video_id)
    selected_chunk_ids = parse_chunk_ids(args.chunks)

    if args.force_download:
        (AUDIO_DIR / f"{args.platform}_{video_id}.m4a").unlink(missing_ok=True)
        (AUDIO_DIR / f"{args.platform}_{video_id}.json").unlink(missing_ok=True)
        (WAV_DIR / f"{video_id}.wav").unlink(missing_ok=True)
        run_dir = RUNS_DIR / run_key(video_id, args)
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)

    try:
        meta = fetch_metadata(args.source, args.platform, video_id)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    duration = meta.get("duration") or 0
    chapters = extract_chapters_from_meta(meta)

    # ---- 快速路线一：针对 --chunk-index 模式（构建 L0 / L0-A / L0-B 智能导航）----
    if args.chunk_index:
        # 1. 字幕快车道 (L0-subtitle)
        if args.mode in ("auto", "subtitle"):
            picked = pick_subtitle(meta, prefer_lang=args.language)
            if picked:
                lang, entry, is_auto = picked
                sub_text = fetch_subtitle_text(entry, args.platform)
                if sub_text:
                    sub_segs = []
                    cur_sec = 0.0
                    for line in sub_text.splitlines():
                        m = re.match(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)", line)
                        if m:
                            cur_sec = parse_ts(m.group(1))
                            sub_segs.append({"start": cur_sec, "text": m.group(2).strip()})
                        elif line.strip():
                            sub_segs.append({"start": cur_sec, "text": line.strip()})
                    chunk_index = generate_chunk_index_from_segments(sub_segs, duration, args.chunk_len, chapters=chapters)
                    idx_payload = {
                        "video_id": video_id,
                        "title": meta.get("title", ""),
                        "duration": duration,
                        "duration_str": fmt_ts(duration),
                        "content_source": f"subtitle:{lang}",
                        "nav_level": "L0-subtitle",
                        "chunk_count": len(chunk_index),
                        "chunk_index": chunk_index,
                    }
                    return _output_chunk_index(idx_payload, args, video_id)

        # 2. 已有转录断点时的 chunk-index (L0-manifest)
        run_dir = RUNS_DIR / run_key(video_id, args)
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                chunk_index = generate_chunk_index(run_dir, manifest, chapters=chapters)
                idx_payload = {
                    "video_id": video_id,
                    "title": meta.get("title", ""),
                    "duration": duration,
                    "duration_str": fmt_ts(duration),
                    "content_source": "whisper",
                    "nav_level": "L0-manifest",
                    "chunk_count": len(chunk_index),
                    "chunk_index": chunk_index,
                }
                return _output_chunk_index(idx_payload, args, video_id)
            except Exception:
                pass

        # 3. 免费元数据导航 (L0-A: Chapters / Description Timestamps)
        if chapters:
            chunk_index = generate_chunk_index_from_chapters(chapters, duration, args.chunk_len)
            idx_payload = {
                "video_id": video_id,
                "title": meta.get("title", ""),
                "duration": duration,
                "duration_str": fmt_ts(duration),
                "content_source": "chapters",
                "nav_level": "L0-A (chapters)",
                "chunk_count": len(chunk_index),
                "chunk_index": chunk_index,
            }
            return _output_chunk_index(idx_payload, args, video_id)

        # 4. 低成本粗侦察 (L0-B: Audio Scout 采样 20s 极速粗转录)
        if args.scout:
            chunks = plan_chunks(duration, args.chunk_len)
            chunk_index = scout_audio_chunks(args.source, args.platform, video_id, meta, chunks, run_dir, args)
            idx_payload = {
                "video_id": video_id,
                "title": meta.get("title", ""),
                "duration": duration,
                "duration_str": fmt_ts(duration),
                "content_source": "whisper_scout",
                "nav_level": "L0-B (audio scout)",
                "chunk_count": len(chunk_index),
                "chunk_index": chunk_index,
            }
            return _output_chunk_index(idx_payload, args, video_id)

        # 5. 兜底纯时间划分
        chunks = plan_chunks(duration, args.chunk_len)
        chunk_index = [{
            "id": c["id"], "start": fmt_ts(c["t0"]), "end": fmt_ts(c["t1"]),
            "duration_s": round(c["t1"] - c["t0"], 1), "status": "pending",
            "chars": 0, "keywords": [], "topic_hints": [], "density": 0.0,
            "has_code": False, "has_formula": False, "has_warning": False,
        } for c in chunks]
        idx_payload = {
            "video_id": video_id,
            "title": meta.get("title", ""),
            "duration": duration,
            "duration_str": fmt_ts(duration),
            "content_source": "none",
            "nav_level": "L0-empty",
            "chunk_count": len(chunk_index),
            "chunk_index": chunk_index,
        }
        return _output_chunk_index(idx_payload, args, video_id)

    content_source = ""
    raw_text = ""
    dehydrated_text = ""
    traps_raw = []
    stats = {"raw_chars": 0, "clean_chars": 0, "compression_ratio": "0%", "traps_count": 0}
    full_raw_text = ""
    full_dehydrated_text = ""
    full_traps_raw = []
    full_stats = None

    # ---- 路线一：真正的字幕快车道（秒级直达，零音频下载）----
    if args.mode in ("auto", "subtitle"):
        picked = pick_subtitle(meta, prefer_lang=args.language)
        if picked:
            lang, entry, is_auto = picked
            print(f"[sub] ⚡ 命中字幕轨道：{lang}{'（AI）' if is_auto else '（人工）'}，秒级直达（跳过音频下载）...", file=sys.stderr)
            sub_text = fetch_subtitle_text(entry, args.platform)
            if sub_text:
                content_source = f"subtitle:{lang}"
                sub_segs = []
                cur_sec = 0.0
                for line in sub_text.splitlines():
                    m = re.match(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)", line)
                    if m:
                        cur_sec = parse_ts(m.group(1))
                        sub_segs.append({"start": cur_sec, "text": m.group(2).strip()})
                    elif line.strip():
                        sub_segs.append({"start": cur_sec, "text": line.strip()})

                full_sub_segs = list(sub_segs)
                full_raw_text = "\n".join(f"[{fmt_ts(s['start'])}] {s['text']}" for s in full_sub_segs)
                full_dehydrated_text, full_traps_raw, full_stats = dehydrate_segments(full_sub_segs, is_subtitle=True)

                if selected_chunk_ids is not None:
                    chunks_plan = plan_chunks(duration, args.chunk_len)
                    valid_spans = [(c["t0"], c["t1"]) for c in chunks_plan if c["id"] in selected_chunk_ids]
                    sub_segs = [s for s in sub_segs if any(t0 <= s.get("start", 0.0) < t1 for t0, t1 in valid_spans)]
                    print(f"[chunks] 仅提取指定分块 {selected_chunk_ids}，过滤后保留 {len(sub_segs)} 个字幕片段", file=sys.stderr)

                raw_text = "\n".join(f"[{fmt_ts(s['start'])}] {s['text']}" for s in sub_segs)
                dehydrated_text, traps_raw, stats = dehydrate_segments(sub_segs, is_subtitle=True)
            elif args.mode == "subtitle":
                print("[error] 找到字幕轨道但网络抓取字幕文本失败，且指定了 --mode subtitle", file=sys.stderr)
                return 1
        elif args.mode == "subtitle":
            print(f"[error] 未找到可用字幕（偏好语言: {args.language}），且指定了 --mode subtitle", file=sys.stderr)
            return 1

    # ---- 路线二：P0 真实切片续传音频转录（仅在无字幕或显式 audio 模式时下载音频）----
    if not raw_text and args.mode in ("auto", "audio"):
        m4a, meta = ensure_audio(args.source, args.platform, video_id, existing_meta=meta)
        content_source = "whisper"
        wav = ensure_wav16k(m4a, video_id)
        if not duration:
            duration = get_audio_duration(wav)

        total_chunks = len(plan_chunks(duration, args.chunk_len))
        print(f"[info] 时长: {fmt_ts(duration)}，切片: {args.chunk_len:.0f}s/块 → 共 {total_chunks} 块", file=sys.stderr)

        run_dir = RUNS_DIR / run_key(video_id, args)
        if args.force and run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = run_dir / "manifest.json"

        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            old_params = manifest.get("params", {})
            curr_params = vars(args)
            critical_keys = ["model", "chunk_len", "language", "vad", "beam_size", "domain_prompt"]
            mismatched = [k for k in critical_keys if str(old_params.get(k)) != str(curr_params.get(k))]
            if mismatched:
                print(f"[resume] ⚠️ 断点参数不一致 ({', '.join(mismatched)})，拒绝混跑旧检查点，自动从头重转...", file=sys.stderr)
                shutil.rmtree(run_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                manifest = {"version": 1, "video_id": video_id, "duration": duration,
                            "params": vars(args), "chunks": plan_chunks(duration, args.chunk_len)}
                atomic_write_json(manifest_path, manifest)
            else:
                reverted = 0
                for c in manifest["chunks"]:
                    if c["status"] == "done" and not (run_dir / c["file"]).exists():
                        print(f"[resume] ⚠️ chunk {c['id']:04d} 标记完成但分块文件缺失，重置为待转录", file=sys.stderr)
                        c["status"] = "pending"
                        reverted += 1
                if reverted > 0:
                    atomic_write_json(manifest_path, manifest)
                done_n = sum(c["status"] == "done" for c in manifest["chunks"])
                print(f"[resume] ⚡ 检测到断点：已完成 {done_n}/{len(manifest['chunks'])} 块，无缝续跑剩余部分", file=sys.stderr)
        else:
            manifest = {"version": 1, "video_id": video_id, "duration": duration,
                        "params": vars(args), "chunks": plan_chunks(duration, args.chunk_len)}
            atomic_write_json(manifest_path, manifest)

        device, compute_type = resolve_device(args.device, args.compute_type)
        print(f"[model] 加载模型 {args.model}（device={device}, compute_type={compute_type}）...", file=sys.stderr)
        model, model_ref = load_whisper_model(args.model, device=device, compute_type=compute_type, model_source=args.model_source)

        language = None if args.language in ("auto", "none") else args.language
        if language is None:
            language, model = detect_language(model, model_ref, wav, run_dir, vad=args.vad, duration=duration)

        if selected_chunk_ids is not None:
            target_chunks = [c for c in manifest["chunks"] if c["id"] in selected_chunk_ids]
            print(f"[chunks] 仅转录指定分块: {selected_chunk_ids} (共 {len(target_chunks)} 块)", file=sys.stderr)
        else:
            target_chunks = manifest["chunks"]

        pending = [c for c in target_chunks if c["status"] != "done"]
        outer = tqdm(pending, desc="chunks", unit="块",
                     bar_format="{desc} {n_fmt}/{total_fmt}块 [{elapsed}<{remaining}]")
        for c in outer:
            outer.set_postfix_str(f"{fmt_ts(c['t0'])}→{fmt_ts(c['t1'])}")
            segs, model = transcribe_chunk(model, model_ref, wav, c, args, language, run_dir)
            atomic_write_json(run_dir / c["file"], {"segments": segs})
            c["status"] = "done"
            atomic_write_json(manifest_path, manifest)

        # 归档只收"已转录完成的块"，而不是要求全部分块就位：
        # --chunks 模式下未选中的块本来就没文件，写死 selected_chunk_ids=None
        # 会让这里直接抛"分块文件缺失"，把正常用法判成失败。
        # 用户实际要的那几块由下面 merge(selected_chunk_ids=...) 严格把关，
        # 缺一块就报错——两处一松一紧，各司其职。
        archived_ids = transcribed_chunk_ids(run_dir, manifest)
        if len(archived_ids) < len(manifest["chunks"]):
            print(f"[archive] 已转录 {len(archived_ids)}/{len(manifest['chunks'])} 块，"
                  f"归档仅包含已转录部分（--chunks 部分提取模式下属正常）", file=sys.stderr)
        full_merged_segs = merge(run_dir, manifest, selected_chunk_ids=archived_ids)
        full_raw_lines = [f"[{fmt_ts(s['start'])}] {s['text']}" for s in full_merged_segs]
        full_raw_text = "\n".join(full_raw_lines)
        full_dehydrated_text, full_traps_raw, full_stats = dehydrate_segments(full_merged_segs, is_subtitle=False)

        merged_segs = merge(run_dir, manifest, selected_chunk_ids=selected_chunk_ids)
        raw_lines = [f"[{fmt_ts(s['start'])}] {s['text']}" for s in merged_segs]
        raw_text = "\n".join(raw_lines)
        dehydrated_text, traps_raw, stats = dehydrate_segments(merged_segs, is_subtitle=False)

    content_plain = strip_timestamps(dehydrated_text if dehydrated_text else raw_text)

    dedup_msg = f"，滑动去重扣减 {stats.get('dedup_removed', 0)} 字" if stats.get('dedup_removed') else ""
    print(f"[dehydrate] 统计：原始 {stats.get('raw_chars', 0)} 字{dedup_msg} -> 脱水后 {stats.get('clean_chars', 0)} 字"
          f"（压缩率 {stats.get('compression_ratio', '0%')}，保留陷阱/转折句 {stats.get('traps_count', 0)} 条）", file=sys.stderr)

    # ---- L1.5 证据提炼模式 ----
    evidence_text = ""
    if args.evidence:
        evidence_text, ev_stats = extract_evidence(dehydrated_text, traps_raw)
        stats.update(ev_stats)
        print(f"[evidence] ⚡ L1.5 证据提炼：脱水文本进一步压缩 {ev_stats['evidence_reduction']}，保留核心事实 {ev_stats['evidence_chars']} 字", file=sys.stderr)

    archive_payload = {
        "video_id": video_id,
        "source": args.source,
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "duration": duration,
        "duration_str": fmt_ts(duration),
        "content_source": content_source,
        "content": full_raw_text if full_raw_text else raw_text,
        "content_dehydrated": full_dehydrated_text if full_dehydrated_text else dehydrated_text,
        "content_plain": strip_timestamps(full_dehydrated_text if full_dehydrated_text else full_raw_text if full_raw_text else (dehydrated_text or raw_text)),
        "traps_raw": full_traps_raw if full_traps_raw else traps_raw,
        "stats": full_stats if full_stats else stats,
    }

    llm_payload = {
        "video_id": video_id,
        "source": args.source,
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "duration": duration,
        "duration_str": fmt_ts(duration),
        "content_source": content_source,
        "content_dehydrated": evidence_text if args.evidence else dehydrated_text,
        "traps_raw": traps_raw,
        "stats": stats,
    }
    if args.evidence:
        llm_payload["content_evidence"] = evidence_text
    if args.full_archive:
        llm_payload["content"] = raw_text
        llm_payload["content_plain"] = content_plain

    prefix = Path(args.out) if args.out else RUNS_DIR / run_key(video_id, args) / "output"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    if prefix.suffix in (".json", ".txt"):
        base_prefix = prefix.with_suffix("")
    else:
        base_prefix = prefix

    archive_path = base_prefix.with_name(f"{base_prefix.stem}_archive.json")
    json_path = base_prefix.with_suffix(".json")
    txt_path = base_prefix.with_suffix(".txt")

    atomic_write_json(archive_path, archive_payload)
    atomic_write_json(json_path, llm_payload)
    if not args.json:
        txt_path.write_text(evidence_text if args.evidence else dehydrated_text, encoding="utf-8")

    if args.json and not args.out:
        print(json.dumps(llm_payload, ensure_ascii=False, indent=2))

    print(f"[done] 全链路完成，LLM 上下文结果已写入: {json_path}", file=sys.stderr)
    print(f"[archive] 本地完整证据已持久化存档: {archive_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
