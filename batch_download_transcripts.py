"""
Download and save authentic transcripts for all Cryptography chapters.
UP主：可厉害的土豆 + 西电杨波
"""
import os
import json
import sys
import io

# 强制 Windows 终端使用 UTF-8 输出，防止 emoji 报 GBK 编码错误
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from bili_helper import BilibiliClient

VIDEOS = {
    # 第二章 对称密码体制
    "ch2_des": {"bvid": "BV1KQ4y127AT", "title": "DES加密算法 (可厉害的土豆)"},
    "ch2_modes": {"bvid": "BV1U8411f74f", "title": "分组密码工作模式 (可厉害的土豆)"},
    "ch2_aes": {"bvid": "BV1i341187fK", "title": "AES加密算法 (可厉害的土豆)"},
    "ch2_zuc": {"bvid": "BV1xG4y1v7pK", "title": "ZUC祖冲之算法 (可厉害的土豆)"},
    
    # 第三章 公钥密码体制
    "ch3_rsa": {"bvid": "BV1YQ4y1a7n1", "title": "RSA加密算法 (可厉害的土豆)"},
    "ch3_ecc": {"bvid": "BV1v44y1b7Fd", "title": "ECC椭圆曲线密码 (可厉害的土豆)"},
    "ch3_sm2": {"bvid": "BV1ML4y1H7gx", "title": "SM2公钥算法 (可厉害的土豆)"},

    # 西电杨波 现代密码学
    "yangbo_crypto": {"bvid": "BV1qwFNz4EP3", "title": "西电杨波 现代密码学公开课"}
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "transcripts")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    client = BilibiliClient()
    
    print(f"开始批量获取真实原片视频转录文本...")
    for key, info in VIDEOS.items():
        bvid = info["bvid"]
        title = info["title"]
        target_file = os.path.join(OUT_DIR, f"{key}_{bvid}.json")
        if os.path.exists(target_file):
            print(f"[-] 已存在跳过: {title} ({bvid})")
            continue
        
        print(f"[+] 正在从 B站 提取: {title} ({bvid})...")
        try:
            res = client.get_transcript(bvid)
            if "transcript" in res and res["transcript"]:
                data = {
                    "key": key,
                    "bvid": bvid,
                    "title": title,
                    "data_source": res.get("data_source"),
                    "transcript": res["transcript"]
                }
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"    ✅ 成功获取转录文本，字数: {len(res['transcript'])}")
            else:
                print(f"    ⚠️ 未获取到字幕: {res.get('error') or res}")
        except Exception as e:
            print(f"    ❌ 获取失败: {e}")

    client.close()
    print("全部原片转录文本下载完毕！")

if __name__ == "__main__":
    main()
