"""
SoundCloudClient — คุยกับ api-v2.soundcloud.com (ตัวเดียวกับที่หน้าเว็บ SC ใช้)
ฟรี ใช้ client_id ที่ขุดมาจาก JS bundle ของหน้าเว็บ (เหมือนเปิดเว็บปกติ)

หลักที่รักษาไว้ตาม README:
  - read-only, ใส่ sleep/backoff เสมอ
  - ไม่ hardcode credential (client_id auto, oauth ผ่าน env)
"""

import re
import time
import requests

API = "https://api-v2.soundcloud.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


class SoundCloudError(RuntimeError):
    pass


class SoundCloudClient:
    def __init__(self, oauth_token: str = "", client_id_override: str = "",
                 sleep: float = 0.4, max_retries: int = 3):
        self.oauth_token = oauth_token
        self.client_id_override = client_id_override
        self.sleep = sleep
        self.max_retries = max_retries
        self._client_id = None
        self.session = requests.Session()
        self.session.headers.update(UA)
        if oauth_token:
            self.session.headers["Authorization"] = f"OAuth {oauth_token}"

    # ---------- client_id ----------
    @property
    def client_id(self) -> str:
        if self._client_id:
            return self._client_id
        if self.client_id_override:
            self._client_id = self.client_id_override
            return self._client_id
        self._client_id = self._scrape_client_id()
        return self._client_id

    def _scrape_client_id(self) -> str:
        html = self.session.get("https://soundcloud.com/", timeout=15).text
        scripts = re.findall(
            r'<script[^>]+src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html)
        for url in reversed(scripts):
            js = self.session.get(url, timeout=15).text
            m = re.search(r'client_id\s*[:=]\s*"([0-9a-zA-Z]{20,})"', js)
            if m:
                return m.group(1)
        raise SoundCloudError(
            "หา client_id ไม่เจอ -> ใส่ auth.client_id_override ใน config")

    # ---------- low-level GET (มี retry/backoff) ----------
    def _get(self, path_or_url: str, params: dict = None):
        url = path_or_url if path_or_url.startswith("http") else f"{API}{path_or_url}"
        params = dict(params or {})
        params.setdefault("client_id", self.client_id)
        last = None
        for attempt in range(self.max_retries):
            r = self.session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 502, 503):     # rate limit / transient
                time.sleep(self.sleep * (2 ** attempt) + 1)
                last = r
                continue
            last = r
            break
        raise SoundCloudError(
            f"HTTP {last.status_code if last else '?'} จาก {url} "
            f"(ถ้า likes private ลองใส่ oauth_token)")

    # ---------- API methods ----------
    def resolve(self, url: str) -> dict:
        return self._get("/resolve", {"url": url})

    def resolve_user_id(self, profile_url: str) -> int:
        d = self.resolve(profile_url)
        if d.get("kind") != "user":
            raise SoundCloudError(f"{profile_url} ไม่ใช่หน้า user")
        return d["id"]

    def resolve_track(self, track_url: str):
        """แปลงลิงก์เพลง -> track dict (None ถ้าไม่ใช่ track)"""
        try:
            d = self.resolve(track_url)
        except SoundCloudError:
            return None
        return d if d.get("kind") == "track" else None

    def get_liked_tracks(self, user_id: int, max_seeds: int) -> list:
        url = "/me/track_likes" if self.oauth_token else f"/users/{user_id}/track_likes"
        params = {"limit": 50, "linked_partitioning": 1}
        seeds, next_url = [], url
        while next_url and len(seeds) < max_seeds:
            data = self._get(next_url, params)
            for item in data.get("collection", []):
                t = item.get("track", item)   # บาง endpoint ห่อใน 'track'
                if t and t.get("kind") == "track":
                    seeds.append(t)
            next_url = data.get("next_href")
            params = {}                       # next_href มี param ครบแล้ว
            time.sleep(self.sleep)
        return seeds[:max_seeds]

    def get_related(self, track_id: int, limit: int) -> list:
        try:
            data = self._get(f"/tracks/{track_id}/related", {"limit": limit})
        except SoundCloudError:
            return []
        return data.get("collection", [])
