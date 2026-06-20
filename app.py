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
import os
import secrets
from dataclasses import replace

from flask import (Flask, jsonify, render_template, request, send_file, abort,
                   session, redirect, url_for, make_response)

from scfinder import load_config, find_references, SeenStore
from scfinder.finder import COLUMNS
from scfinder.client import SoundCloudClient, SoundCloudError
from scfinder.mockclient import MockClient
from scfinder.export import EXPORTERS
from scfinder.notify import notify_line_results
from scfinder.feedback import FeedbackStore, PreferenceModel, annotate_and_rank
from scfinder.storage import make_storage
from scfinder.crate import Crate
from scfinder.resolver import classify

app = Flask(__name__)
BASE_CFG = load_config()
app.secret_key = BASE_CFG.secret_key or secrets.token_hex(16)
STORAGE = make_storage(BASE_CFG)     # None = ใช้ไฟล์ local ; ไม่ None = Supabase
_last = {"csv": "", "results": []}   # เก็บผลรันล่าสุดไว้ export
FEEDBACK_FILE = "feedback.json"


def _results_csv(results) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for r in results:
        w.writerow(r.as_row())
    return buf.getvalue()


def _set_last(results, persist=True):
    """เก็บผลรันล่าสุดไว้ใน memory + (ถ้ามี Supabase) เก็บถาวรไว้กู้ข้ามเครื่อง/รีสตาร์ท"""
    _last["results"] = results
    _last["csv"] = _results_csv(results)
    if persist and STORAGE and hasattr(STORAGE, "save_state"):
        try:
            STORAGE.save_state("last_results", [r.__dict__ for r in results])
        except Exception:
            pass


def _restore_last():
    """กู้ผลรันล่าสุดจาก Supabase ถ้า memory ว่าง (เช่นหลัง Render รีสตาร์ท / เปิดจากเครื่องอื่น)"""
    if _last["results"] or not (STORAGE and hasattr(STORAGE, "load_state")):
        return
    data = STORAGE.load_state("last_results")
    if not data:
        return
    from scfinder.finder import Result
    try:
        results = [Result(**d) for d in data]
    except (TypeError, ValueError):
        return
    _set_last(results, persist=False)


# ---------- auth (เปิดเมื่อมี APP_PASSWORD) ----------
APP_PASSWORD = BASE_CFG.app_password


@app.before_request
def _guard():
    if not APP_PASSWORD:                       # ไม่ตั้งรหัส = เปิดโล่ง (dev)
        return
    if request.endpoint == "static" or request.path in ("/login", "/sw.js"):
        return
    if session.get("auth"):
        return
    if request.path.startswith(("/api", "/export")) or request.path == "/download":
        return abort(401)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not APP_PASSWORD:
        return redirect(url_for("index"))
    err = ""
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["auth"] = True
            session.permanent = True
            return redirect(url_for("index"))
        err = "รหัสผ่านไม่ถูกต้อง"
    return render_template("login.html", err=err)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


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
        bpm_min=num("bpm_min", BASE_CFG.bpm_min, float),
        bpm_max=num("bpm_max", BASE_CFG.bpm_max, float),
        fresh_cap=max(0.0, min(1.0, num("fresh_pct", BASE_CFG.fresh_cap * 100, float) / 100.0)),
        dedupe_enabled=bool(form.get("dedupe_enabled")),
        demo_mode=bool(form.get("demo_mode")),
        sleep=0.0 if form.get("demo_mode") else BASE_CFG.sleep,
    )


@app.route("/sw.js")
def service_worker():
    resp = make_response(app.send_static_file("sw.js"))
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Service-Worker-Allowed"] = "/"     # ให้ scope ครอบ "/"
    return resp


@app.route("/")
def index():
    return render_template("dashboard.html", cfg=BASE_CFG.to_public_dict())


@app.route("/api/run", methods=["POST"])
def api_run():
    form = request.get_json(silent=True) or request.form
    cfg = cfg_from_form(form)

    logs = []
    client = build_client(cfg)
    store = SeenStore(cfg.seen_file, cfg.dedupe_enabled, storage=STORAGE)

    # known-set: เพลงที่ "เคยรู้จัก" (เคยปัดในแอป + like บน SoundCloud) ไว้คุมสัดส่วนไม่ให้ผลมีเพลงเก่าเยอะ
    known_ids = set()
    if not cfg.demo_mode and 0 < cfg.fresh_cap < 1:
        try:
            known_ids |= set(FeedbackStore(FEEDBACK_FILE, storage=STORAGE).rated_ids())
        except Exception:
            pass
        if hasattr(client, "get_liked_track_ids") and "YOUR-HANDLE" not in cfg.profile_url:
            try:
                uid = client.resolve_user_id(cfg.profile_url)
                known_ids |= client.get_liked_track_ids(uid, limit=300)
            except Exception:
                pass

    try:
        results = find_references(client, cfg, store, log=logs.append, known_ids=known_ids)
    except (SoundCloudError, ValueError) as e:
        return jsonify({"ok": False, "error": str(e), "logs": logs}), 200

    store.save()

    _set_last(results)

    return jsonify({
        "ok": True,
        "count": len(results),
        "demo": cfg.demo_mode,
        "logs": logs,
        "results": [r.__dict__ for r in results],
    })


@app.route("/download")
def download():
    data = _last["csv"] or "no data — run ก่อน\n"
    return send_file(
        io.BytesIO(data.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="sc_references.csv",
    )


@app.route("/export/<fmt>")
def export(fmt):
    """export ผลรันล่าสุดเป็นฟอร์แมตอื่น (Mixed In Key CSV / M3U8 / JSON)"""
    if fmt not in EXPORTERS:
        abort(404)
    func, mime, fname = EXPORTERS[fmt]
    data = func(_last["results"]) if _last["results"] else ""
    return send_file(
        io.BytesIO(data.encode("utf-8")),
        mimetype=mime,
        as_attachment=True,
        download_name=fname,
    )


@app.route("/api/notify", methods=["POST"])
def api_notify():
    """ส่งผลรันล่าสุดเข้า LINE (ใช้ LINE_CHANNEL_TOKEN/LINE_TO จาก env)"""
    if not _last["results"]:
        return jsonify({"ok": False, "info": "ยังไม่มีผล — Run ก่อน"}), 200
    from datetime import datetime
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    cfg = load_config()   # อ่าน token ล่าสุดจาก env
    ok, info = notify_line_results(_last["results"], cfg, when=when)
    return jsonify({"ok": ok, "info": info})


# ========== Phase 4: Tinder-style feedback + learning ==========
def _profile_payload(store: FeedbackStore) -> dict:
    model = PreferenceModel(store.records)
    return {"counts": store.counts(), "profile": model.profile()}


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """บันทึก 1 การปัด (like/dislike) + คืน taste profile ล่าสุด"""
    data = request.get_json(silent=True) or {}
    track = data.get("track") or {}
    if not (track.get("track_id") or track.get("id")):
        return jsonify({"ok": False, "info": "ไม่มี track"}), 200
    store = FeedbackStore(FEEDBACK_FILE, storage=STORAGE)
    store.record(track, bool(data.get("liked")))
    store.save()
    return jsonify({"ok": True, **_profile_payload(store)})


@app.route("/api/profile")
def api_profile():
    """taste profile + รายการ track_id ที่ปัดแล้ว (ไว้ข้ามใน swipe queue)"""
    store = FeedbackStore(FEEDBACK_FILE, storage=STORAGE)
    return jsonify({"ok": True, "rated": sorted(store.rated_ids()),
                    **_profile_payload(store)})


@app.route("/api/last")
def api_last():
    """ผลรันล่าสุด — ไว้กู้ตอนเปิดหน้า/รีเฟรช/เปิดจากอีกเครื่อง (ไม่ต้อง Run ใหม่)"""
    _restore_last()
    res = _last["results"]
    return jsonify({"ok": True, "count": len(res),
                    "results": [r.__dict__ for r in res]})


@app.route("/api/history")
def api_history():
    """ประวัติทุกเพลงที่เคยกด like/dislike (ใหม่สุดก่อน)"""
    store = FeedbackStore(FEEDBACK_FILE, storage=STORAGE)
    recs = sorted(store.records, key=lambda r: r.get("when", ""), reverse=True)
    return jsonify({"ok": True, "records": recs, **_profile_payload(store)})


@app.route("/api/rate_toggle", methods=["POST"])
def api_rate_toggle():
    """สลับ like<->dislike ของเพลงที่เคยปัด (คง features/title เดิมไว้)"""
    from datetime import datetime, timezone
    data = request.get_json(silent=True) or {}
    tid = str(data.get("track_id", ""))
    store = FeedbackStore(FEEDBACK_FILE, storage=STORAGE)
    rec = next((r for r in store.records if str(r["track_id"]) == tid), None)
    if not rec:
        return jsonify({"ok": False, "info": "ไม่พบรายการ"}), 200
    rec["liked"] = not rec["liked"]
    rec["when"] = datetime.now(timezone.utc).isoformat()
    store.save()
    return jsonify({"ok": True, **_profile_payload(store)})


@app.route("/api/rerank", methods=["POST"])
def api_rerank():
    """จัดอันดับผลรันล่าสุดใหม่ด้วยรสนิยมที่เรียนรู้ (co-occurrence ยังนำ)"""
    if not _last["results"]:
        return jsonify({"ok": False, "info": "ยังไม่มีผล — Run ก่อน"}), 200
    store = FeedbackStore(FEEDBACK_FILE, storage=STORAGE)
    if not store.records:
        return jsonify({"ok": False, "info": "ยังไม่มี feedback — ปัดเพลงก่อน"}), 200
    ranked = annotate_and_rank(_last["results"], store.records, weight=0.5)
    _set_last(ranked)
    return jsonify({"ok": True, "count": len(ranked),
                    "results": [r.__dict__ for r in ranked]})


# ========== Phase 1-4: Crate (คิวโหลดเพลง — สั่งจากมือถือได้) ==========
@app.route("/api/crate", methods=["POST"])
def api_crate_add():
    """
    เพิ่มเพลงเข้าคิวโหลด (resolver จำแนก route ให้). รับได้หลายแบบ:
      {top_n:N} | {track_ids:[...]} (เลือกจากผลรันล่าสุด) | {tracks:[...]} | {track:{...}}
    """
    data = request.get_json(silent=True) or {}
    crate = Crate(BASE_CFG.crate_file, storage=STORAGE)

    tracks = []
    if data.get("top_n"):
        _restore_last()
        tracks = [r.__dict__ for r in _last["results"][:int(data["top_n"])]]
    elif data.get("track_ids"):
        _restore_last()
        idset = {str(t) for t in data["track_ids"]}
        tracks = [r.__dict__ for r in _last["results"] if str(r.track_id) in idset]
    elif data.get("tracks"):
        tracks = data["tracks"]
    elif data.get("track"):
        tracks = [data["track"]]

    added = 0
    for t in tracks:
        route, target = classify(t)
        if crate.add(t, route=route, target_url=target):
            added += 1
    crate.save()
    return jsonify({"ok": True, "added": added, "counts": crate.counts()})


@app.route("/api/crate")
def api_crate_list():
    """รายการคิว + สถานะ (dashboard poll ดูความคืบหน้า / สถานะ done จาก Mac)"""
    crate = Crate(BASE_CFG.crate_file, storage=STORAGE)
    recs = sorted(crate.records, key=lambda r: r.get("when", ""), reverse=True)
    return jsonify({"ok": True, "counts": crate.counts(), "records": recs})


@app.route("/api/crate/clear", methods=["POST"])
def api_crate_clear():
    """ลบรายการที่จบแล้ว (เก็บเฉพาะ pending/downloading)"""
    crate = Crate(BASE_CFG.crate_file, storage=STORAGE)
    crate.clear_finished()
    crate.save()
    return jsonify({"ok": True, "counts": crate.counts()})


@app.route("/api/crate/requeue", methods=["POST"])
def api_crate_requeue():
    """ลองโหลดใหม่ (Review loop — เพลงที่ failed/low_quality)"""
    data = request.get_json(silent=True) or {}
    crate = Crate(BASE_CFG.crate_file, storage=STORAGE)
    rec = crate._find(data.get("track_id"))
    if not rec:
        return jsonify({"ok": False, "info": "ไม่พบในคิว"}), 200
    crate.add(rec, requeue=True)
    crate.save()
    return jsonify({"ok": True, "counts": crate.counts()})


if __name__ == "__main__":
    import os
    # PORT มาจาก host (Render/HF/Railway) ; default 5000 ตอนรันในเครื่อง
    port = int(os.environ.get("PORT", 5000))
    # host=0.0.0.0 เพื่อให้เข้าถึงได้จากภายนอกตอน deploy
    app.run(host="0.0.0.0", port=port, debug=False)
