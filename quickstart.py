#!/usr/bin/env python3
"""
quickstart — ตั้งค่า + ต่อ SoundCloud จริง แบบกดทีเดียว

รัน:  python3 quickstart.py

ทำให้อัตโนมัติ:
  1) ติดตั้ง dependencies (ถ้ายังไม่มี)
  2) ถาม seed (วางลิงก์เพลงที่ชอบ หรือใช้ likes จากโปรไฟล์)
  3) เขียน config.yaml ให้ + ปิด demo_mode อัตโนมัติ
  4) (ถ้าจำเป็น) ใส่ SC_OAUTH_TOKEN ลง .env ให้
  5) รัน doctor.py เช็คว่าต่อ SoundCloud ติดจริง
  6) เปิด dashboard / รัน CLI ให้เลย
"""

import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))


def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    try:
        s = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        s = ""
    return s or default


def ensure_deps():
    try:
        import yaml, requests, bs4, flask  # noqa: F401
        return
    except ImportError:
        print("• ติดตั้ง dependencies (ครั้งแรกอาจช้าหน่อย)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r",
             os.path.join(ROOT, "requirements.txt")]
        )
        print("  ✓ ติดตั้งเสร็จ\n")


def collect_urls():
    print("\nวางลิงก์เพลงที่ชอบจาก SoundCloud (ทีละบรรทัด) — เสร็จแล้วกด Enter ว่างๆ 1 ที")
    urls = []
    while True:
        try:
            line = input(f"  เพลง #{len(urls) + 1}: ").strip()
        except EOFError:
            break
        if not line:
            break
        if "soundcloud.com" not in line:
            print("    ⚠ ดูไม่เหมือนลิงก์ SoundCloud — ข้ามนะ (ต้องมี soundcloud.com)")
            continue
        urls.append(line)
    return urls


def upsert_env(key, value):
    """เขียน key=value ลง .env (อัปเดตถ้ามีอยู่แล้ว, ไม่งั้น append)"""
    env_path = os.path.join(ROOT, ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  ✓ บันทึก {key} ลง .env แล้ว")


def main():
    print("=" * 48)
    print("  SoundCloud Reference Finder — quickstart")
    print("=" * 48)
    ensure_deps()
    import yaml

    cfg_path = os.path.join(ROOT, "config.yaml")
    ex_path = os.path.join(ROOT, "config.example.yaml")
    src = cfg_path if os.path.exists(cfg_path) else ex_path
    with open(src, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    print(f"\nอ่านค่าเดิมจาก: {os.path.basename(src)}")

    # --- seed mode ---
    print("\nเลือกวิธีหาเพลง (seed):")
    print("  [1] วางลิงก์เพลงที่ชอบเอง  (ง่ายสุด ไม่ต้อง login)")
    print("  [2] ใช้ likes จากโปรไฟล์ของคุณ")
    print("  [3] ใช้ทั้งสองอย่างรวมกัน")
    choice = ask("เลือก 1/2/3", "1")
    mode = {"1": "urls", "2": "likes", "3": "both"}.get(choice, "urls")
    cfg["seed_mode"] = mode

    if mode in ("urls", "both"):
        urls = collect_urls()
        if urls:
            cfg["seed_urls"] = urls
            print(f"  ✓ รับมา {len(urls)} เพลง")
        elif not cfg.get("seed_urls"):
            print("  ⚠ ยังไม่มีลิงก์เพลงเลย — เดี๋ยว doctor จะเตือน")

    if mode in ("likes", "both"):
        cur = cfg.get("profile_url", "")
        if "YOUR-HANDLE" in cur:
            cur = ""
        prof = ask("\nลิงก์โปรไฟล์ SoundCloud ของคุณ (เช่น https://soundcloud.com/your-handle)", cur)
        if prof:
            cfg["profile_url"] = prof
        token = ask("likes เป็น private ไหม? ถ้าใช่วาง SC_OAUTH_TOKEN (ไม่มีก็เว้นว่าง)", "")
        if token:
            upsert_env("SC_OAUTH_TOKEN", token)

    # --- ปิด demo เสมอ (นี่คือ "การต่อจริง") ---
    cfg["demo_mode"] = False

    # --- เขียน config.yaml ---
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write("# สร้างโดย quickstart.py — คำอธิบายแต่ละค่าดูได้ใน config.example.yaml\n")
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    print(f"\n✓ เขียน config.yaml แล้ว (seed_mode={mode}, demo_mode=false)")

    # --- doctor ---
    print("\n--- เช็คการเชื่อมต่อ (doctor.py) ---")
    rc = subprocess.call([sys.executable, os.path.join(ROOT, "doctor.py")])
    if rc != 0:
        print("\n✗ ยังต่อ SoundCloud ไม่ครบ — แก้ตามที่ doctor บอกด้านบน")
        print("  แล้วรันใหม่:  python3 quickstart.py   (หรือเช็คซ้ำ: python3 doctor.py)")
        return 1

    # --- run ---
    print("\nต่อ SoundCloud ได้แล้ว 🎉  จะรันแบบไหนต่อ?")
    print("  [1] Dashboard เว็บ (http://127.0.0.1:5000)")
    print("  [2] CLI (สร้าง sc_references.csv)")
    print("  [3] ยังไม่รัน เดี๋ยวรันเอง")
    run = ask("เลือก 1/2/3", "1")
    if run == "1":
        print("เปิด http://127.0.0.1:5000 ในเบราว์เซอร์ (กด Ctrl+C เพื่อหยุด)")
        subprocess.call([sys.executable, os.path.join(ROOT, "app.py")])
    elif run == "2":
        subprocess.call([sys.executable, os.path.join(ROOT, "sc_reference_finder.py")])
    else:
        print("รันเองได้ทีหลัง:  python3 app.py   หรือ   python3 sc_reference_finder.py")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nยกเลิก")
        sys.exit(130)
