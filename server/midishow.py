"""
MidiShow scraper — handles login, search, and MIDI file download.
Uses requests.Session to maintain authenticated cookies.
"""

import os
import re
import time
import threading

import requests
from bs4 import BeautifulSoup

BASE = "https://www.midishow.com"
SEARCH_URL = f"{BASE}/search/result"
LOGIN_URL = f"{BASE}/user/account/login"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class MidiShowClient:
    def __init__(self, username: str, password: str):
        self._user = username
        self._pass = password
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": UA})
        self._logged_in = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ login

    def login(self) -> bool:
        with self._lock:
            return self._do_login()

    def _do_login(self) -> bool:
        try:
            r = self._session.get(LOGIN_URL, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            form = soup.find("form", {"id": "login-form"})
            if not form:
                form = soup.find("form", {"action": re.compile(r"login", re.I)})

            csrf = ""
            csrf_input = (form or soup).find("input", {"name": "_csrf"})
            if csrf_input:
                csrf = csrf_input.get("value", "")
            if not csrf:
                meta = soup.find("meta", {"name": "csrf-token"})
                if meta:
                    csrf = meta.get("content", "")

            payload = {
                "_csrf": csrf,
                "LoginForm[identity]": self._user,
                "LoginForm[password]": self._pass,
            }

            if form:
                for inp in form.find_all("input"):
                    name = inp.get("name")
                    if name and name not in payload:
                        payload[name] = inp.get("value", "")

            action = LOGIN_URL
            if form and form.get("action"):
                act = form["action"]
                if act.startswith("http"):
                    action = act
                elif act.startswith("/"):
                    action = BASE + act

            r2 = self._session.post(
                action, data=payload, timeout=15, allow_redirects=True
            )

            if "logout" in r2.text.lower() or "user/account/logout" in r2.text:
                self._logged_in = True
                return True

            self._logged_in = False
            return False

        except Exception as e:
            print(f"[midishow login error] {e}")
            self._logged_in = False
            return False

    def _ensure_login(self):
        if not self._logged_in:
            self._do_login()

    # ---------------------------------------------------------------- search

    def search(self, query: str, page: int = 1, sort: str = "default") -> dict:
        self._ensure_login()
        try:
            r = self._session.get(
                SEARCH_URL,
                params={"q": query, "page": page, "sort": sort},
                timeout=15,
            )
            r.raise_for_status()
            return self._parse_search(r.text, query, page)
        except Exception as e:
            print(f"[midishow search error] {e}")
            return {"query": query, "page": page, "results": [], "total": 0}

    def _parse_search(self, html: str, query: str, page: int) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        total_text = soup.find(string=re.compile(r"(\d+)\s*条结果|(\d+)\s*results"))
        total = 0
        if total_text:
            m = re.search(r"(\d+)", total_text)
            if m:
                total = int(m.group(1))

        for card in soup.select(".midi-list-item, .search-result-item, .media, article"):
            try:
                item = self._parse_card(card)
                if item and item.get("title"):
                    results.append(item)
            except Exception:
                continue

        if not results:
            results = self._parse_search_fallback(soup)

        return {"query": query, "page": page, "total": total, "results": results}

    def _parse_card(self, card) -> dict:
        item = {}

        link = card.find("a", href=re.compile(r"/midi/"))
        if link:
            item["title"] = link.get_text(strip=True)
            href = link.get("href", "")
            if not href.startswith("http"):
                href = BASE + href
            item["url"] = href

        author_el = card.find("a", href=re.compile(r"/user/|/u/"))
        if author_el:
            item["author"] = author_el.get_text(strip=True)

        text = card.get_text(" ", strip=True)

        size_m = re.search(r"([\d.]+)\s*KB", text)
        if size_m:
            item["size"] = size_m.group(0)

        dur_m = re.search(r"(\d{1,2}:\d{2})", text)
        if dur_m:
            item["duration"] = dur_m.group(1)

        rating_m = re.search(r"([0-5]\.\d)\s*\(", text)
        if rating_m:
            item["rating"] = rating_m.group(1)

        return item

    def _parse_search_fallback(self, soup) -> list:
        """Fallback parser: find all midi links and extract info from surrounding text."""
        results = []
        seen = set()
        for a in soup.find_all("a", href=re.compile(r"/midi/.*download")):
            href = a.get("href", "")
            if href in seen:
                continue
            seen.add(href)
            title = a.get_text(strip=True)
            if not title or len(title) < 2:
                continue
            if not href.startswith("http"):
                href = BASE + href
            item = {"title": title, "url": href, "author": "", "size": "", "duration": "", "rating": ""}

            parent = a.parent
            if parent:
                text = parent.get_text(" ", strip=True)
                size_m = re.search(r"([\d.]+)\s*KB", text)
                if size_m:
                    item["size"] = size_m.group(0)
                dur_m = re.search(r"(\d{1,2}:\d{2})", text)
                if dur_m:
                    item["duration"] = dur_m.group(1)

            results.append(item)
        return results

    # -------------------------------------------------------------- download

    def download(self, midi_page_url: str) -> tuple:
        """
        Download a MIDI file from its detail page URL.
        Three-step flow:
          1. GET detail page → extract midi ID
          2. GET /midi/download?id=X → POST with CSRF → get download-file token
          3. GET /midi/download-file?t=TOKEN → actual .mid binary
        Returns (filename, binary_data) or (None, error_string).
        """
        self._ensure_login()
        try:
            r = self._session.get(midi_page_url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            title = "download"
            title_el = soup.find("h1") or soup.find("title")
            if title_el:
                title = re.sub(r"[<>:\"/\\|?*]", "_", title_el.get_text(strip=True))
                title = title.split("::")[0].split(" - MidiShow")[0].strip()
                if not title:
                    title = "download"

            # Extract midi ID from URL or page
            midi_id = None
            id_match = re.search(r"(\d{4,})", midi_page_url)
            if id_match:
                midi_id = id_match.group(1)
            if not midi_id:
                player = soup.find(attrs={"data-id": True})
                if player:
                    midi_id = player["data-id"]

            if midi_id:
                result = self._download_via_credits(midi_id, title)
                if result[0]:
                    return result

            mid_data = self._try_player_download(soup, r.text)
            if mid_data:
                fname = title if title.endswith(".mid") else title + ".mid"
                return fname, mid_data

            return None, "下载失败：积分不足或服务器未返回有效的 MIDI 文件"

        except Exception as e:
            print(f"[midishow download error] {e}")
            return None, f"下载出错: {e}"

    def _download_via_credits(self, midi_id: str, title: str) -> tuple:
        """Three-step credits-based download."""
        try:
            # Step 1: GET download page
            dl_url = f"{BASE}/midi/download?id={midi_id}"
            r1 = self._session.get(dl_url, timeout=15)
            soup1 = BeautifulSoup(r1.text, "html.parser")

            dl_form = soup1.find("form", {"id": "download-form"})
            if not dl_form:
                return None, "找不到下载表单"

            csrf = ""
            csrf_el = dl_form.find("input", {"name": "_csrf"})
            if csrf_el:
                csrf = csrf_el.get("value", "")

            # Step 2: POST to confirm download (costs credits)
            r2 = self._session.post(dl_url, data={"_csrf": csrf}, timeout=15, allow_redirects=True)
            soup2 = BeautifulSoup(r2.text, "html.parser")

            # Find the download-file link in the response
            file_link = None
            for a in soup2.find_all("a", href=True):
                if "download-file" in a["href"]:
                    file_link = a["href"]
                    break

            if not file_link:
                return None, "确认下载后未找到文件链接（积分可能不足）"

            if not file_link.startswith("http"):
                file_link = BASE + file_link

            # Step 3: GET the actual MIDI file
            r3 = self._session.get(file_link, timeout=30)
            if r3.status_code == 200 and r3.content[:4] == b"MThd":
                cd = r3.headers.get("Content-Disposition", "")
                fname_match = re.search(r'filename="?([^";]+)', cd)
                if fname_match:
                    fname = fname_match.group(1)
                else:
                    fname = title if title.endswith(".mid") else title + ".mid"
                return fname, r3.content

            return None, "服务器未返回有效的 MIDI 文件"
        except Exception as e:
            return None, f"积分下载失败: {e}"

    def _try_player_download(self, soup, html: str) -> bytes | None:
        """Try to extract MIDI data from the web player embed."""
        player = soup.find(class_=re.compile(r"ms-player"))
        if not player:
            player = soup.find(attrs={"data-mid": True})
        if not player:
            return None

        data_mid = player.get("data-mid", "")
        data_id = player.get("data-id", "")
        if not data_mid:
            return None

        try:
            mid_url = data_mid
            mid_url = re.sub(r"^tokeno#:@!", "token", mid_url)
            mid_url = mid_url.replace("www.midishow.com", "s.midishow.net")
            mid_url = mid_url.replace(".mid?", ".js?")
            if not mid_url.startswith("http"):
                mid_url = "https://" + mid_url

            r_js = self._session.get(mid_url, timeout=15)
            if r_js.status_code != 200:
                return None

            js_text = r_js.text
            m = re.search(r'e\("([^"]+)"\)', js_text)
            if not m:
                m = re.search(r"e\('([^']+)'\)", js_text)
            if not m:
                return None
            encoded_data = m.group(1)

            token_url = f"{BASE}/midi/new-file"
            r_tok = self._session.post(
                token_url, data={"id": data_id}, timeout=15
            )
            if r_tok.status_code != 200:
                return None

            etag = r_tok.headers.get("ETag", "").strip('"')
            token_text = r_tok.text

            key = etag + token_text[56:] if len(token_text) > 56 else etag
            if not key:
                return None

            part1 = self._custom_b64(token_text[28:56], key) if len(token_text) >= 56 else ""
            part2 = self._custom_b64(encoded_data, key)
            part3 = self._custom_b64(token_text[:28], key) if len(token_text) >= 28 else ""
            raw = part1 + part2 + part3

            midi_bytes = bytes(ord(c) for c in raw)
            if midi_bytes[:4] == b"MThd":
                return midi_bytes

        except Exception as e:
            print(f"[player download fallback error] {e}")

        return None

    @staticmethod
    def _custom_b64(data: str, key: str) -> str:
        result = []
        i = 0
        while i < len(data):
            o = key.index(data[i]) if i < len(data) and data[i] in key else -1; i += 1
            s = key.index(data[i]) if i < len(data) and data[i] in key else -1; i += 1
            a = key.index(data[i]) if i < len(data) and data[i] in key else -1; i += 1
            u = key.index(data[i]) if i < len(data) and data[i] in key else -1; i += 1
            if o < 0 or s < 0:
                break
            n = (o << 2) | (s >> 4)
            result.append(chr(n))
            if a >= 0 and a != 64:
                ii = ((15 & s) << 4) | (a >> 2)
                result.append(chr(ii))
            if u >= 0 and u != 64:
                r = ((3 & a) << 6) | u
                result.append(chr(r))
        return "".join(result)

    # ---------------------------------------------------------------- status

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
