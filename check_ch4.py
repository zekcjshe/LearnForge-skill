# -*- coding: utf-8 -*-
import glob, os, subprocess

ch4_dir = 'F:/文档/Notion_Obsidian/Notion/备考/笔记簿/08-密码学笔记库/第4章-哈希函数与消息认证码'
archive_path = 'E:/LearnForge-skill/transcripts/ch4_all_transcripts.json'
vault_root = 'F:/文档/Notion_Obsidian/Notion/备考/笔记簿/08-密码学笔记库'

files = sorted(glob.glob(os.path.join(ch4_dir, '*.md')))
print(f"=== 开始全量审计第4章笔记 ({len(files)} 篇) ===")

all_pass = True
for f in files:
    fname = os.path.basename(f)
    res = subprocess.run(
        ['python', 'validate_note.py', f, '--archive', archive_path, '--vault', vault_root],
        cwd='E:/LearnForge-skill',
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    score_line = ""
    gate_line = ""
    for l in res.stdout.splitlines():
        if "质量门禁状态" in l:
            gate_line = l.strip()
    
    passed = "PASSED" in gate_line
    print(f"[{'PASS' if passed else 'FAIL'}] {fname}")
    if gate_line:
        print(f"       {gate_line}")
    if res.stderr and "warning" in res.stderr.lower():
        for l in res.stderr.splitlines():
            if "warning" in l.lower() or "error" in l.lower():
                print(f"       {l.strip()}")
    if not passed:
        all_pass = False
        print(res.stdout)
        print(res.stderr)

print(f"\n全章门禁结果: {'🎉 全部满分通过！' if all_pass else '❌ 存在失败项'}")
