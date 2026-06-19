#!/usr/bin/env python3
"""
Dashboard เว็บ สำหรับ SC Reference Finder
รัน:  python3 app.py   แล้วเปิด http://127.0.0.1:5000

ทำอะไรได้:
  - วางลิงก์เพลง SoundCloud ที่ชอบ (seed) ในช่อง
  - ปรับ config (mode, จำนวน, filter ความยาว, dedupe) จากหน้าเว็บ
  - กด Run -> เห็นตารางผลลัพธ์ เรียงตาม matched_seeds
  - โหลด CSV
  - โหมด demo (ไม่ต่อเน็ต) ไว้ลองหน้าตา/flow ได้ทันที
"""

import io
import csv
from dataclasses import replace

from flask import Flask, jsonify, render_template, request, send_file

from scfinder import load_config, find_references, SeenStore
from scfinder.finder import COLUMNS
from scfinder.client import SoundCloudClient, SoundCloudError
from scfinder.mockclient import MockClient

app = Flask(__name__)
BASE_CFG = load_config()
_last_csv = {"data": ""}   # เก็บ CSV ล่าสุดไว้ให้โหลด


def build_client(cfg):
    if cfg.demo_mode:
        return MockClient()
    return SoundCloudClient(
        oauth_token=cfg.oauth_token,
        client_id_override=cfg.client_id_override,
        sleep=cfg.sleep,
    )


def cfg_from_form(form: dict):
    """สร้าง Config จากค่าในฟอร์ม (override ทับ config.yaml)"""
    def num(key, default, cast):
        try:
            return cast(form.get(key, default))
        except (TypeError, ValueError):
            return default

    urls = [u.strip() for u in (form.get("seed_urls") or "").splitlines() if u.strip()]
    return replace(
        BASE_CFG,
        seed_mode=form.get("seed_mode", BASE_CFG.seed_mode),
        seed_urls=urls or BASE_CFG.seed_urls,
        profile_url=form.get("profile_url") or BASE_CFG.profile_url,
        max_seeds=num("max_seeds", BASE_CFG.max_seeds, int),
        target=num("target", BASE_CFG.target, int),
        related_per_seed=num("related_per_seed", BASE_CFG.related_per_seed, int),
        duration_min=num("duration_min", BASE_CFG.duration_min, float),
        duration_max=num("duration_max", BASE_CFG.duration_max, float),
        dedupe_enabled=bool(form.get("dedupe_enabled")),
        demo_mode=bool(form.get("demo_mode")),
        sleep=0.0 if form.get("demo_mode") else BASE_CFG.sleep,
    )


@app.route("/")
def index():
    return render_template("dashboard.html", cfg=BASE_CFG.to_public_dict())


@app.route("/api/run", methods=["POST"])
def api_run():
    form = request.get_json(silent=True) or request.form
    cfg = cfg_from_form(form)

    logs = []
    client = build_client(cfg)
    store = SeenStore(cfg.seen_file, cfg.dedupe_enabled)

    try:
        results = find_references(client, cfg, store, log=logs.append)
    except (SoundCloudError, ValueError) as e:
        return jsonify({"ok": False, "error": str(e), "logs": logs}), 200

    store.save()

    # เก็บ CSV ไว้ให้ดาวน์โหลด
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for r in results:
        w.writerow(r.as_row())
    _last_csv["data"] = buf.getvalue()

    return jsonify({
        "ok": True,
        "count": len(results),
        "demo": cfg.demo_mode,
        "logs": logs,
        "results": [r.__dict__ for r in results],
    })


@app.route("/download")
def download():
    data = _last_csv["data"] or "no data — run ก่อน\n"
    return send_file(
        io.BytesIO(data.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="sc_references.csv",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
