"""
Unsplash photo fetching with query-hash caching.
Graceful degradation: any failure returns empty dict for that position.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
UNSPLASH_API = "https://api.unsplash.com"
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
PEXELS_API = "https://api.pexels.com/v1"

CACHE_TTL = 86400 * 7  # 7 days


def _query_hash(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode()).hexdigest()[:12]


def _load_cache(cache_dir: Path, hash_key: str) -> dict | None:
    meta_file = cache_dir / f"{hash_key}.json"
    if not meta_file.exists():
        return None
    try:
        meta = json.loads(meta_file.read_text())
        if time.time() - meta.get("cached_at", 0) > CACHE_TTL:
            return None
        img_file = cache_dir / f"{hash_key}.jpg"
        if not img_file.exists():
            return None
        return meta
    except Exception:
        return None


def _save_cache(cache_dir: Path, hash_key: str, meta: dict, img_bytes: bytes) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    meta["cached_at"] = time.time()
    (cache_dir / f"{hash_key}.json").write_text(json.dumps(meta))
    (cache_dir / f"{hash_key}.jpg").write_bytes(img_bytes)


def _fetch_unsplash(query: str, cache_dir: Path, hash_key: str) -> dict | None:
    if not UNSPLASH_ACCESS_KEY:
        return None
    try:
        resp = requests.get(
            f"{UNSPLASH_API}/photos/random",
            params={"query": query, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        img_url = data["urls"]["regular"]
        img_resp = requests.get(img_url, timeout=15)
        img_resp.raise_for_status()

        meta = {
            "url": f"/photo-cache/{hash_key}.jpg",
            "alt": data.get("alt_description") or query,
            "attribution": f'Photo by <a href="{data["user"]["links"]["html"]}?utm_source=research_pipeline&utm_medium=referral">{data["user"]["name"]}</a> on <a href="https://unsplash.com/?utm_source=research_pipeline&utm_medium=referral">Unsplash</a>',
            "source": "unsplash",
        }
        _save_cache(cache_dir, hash_key, meta, img_resp.content)
        return meta
    except Exception as e:
        logger.warning("Unsplash fetch failed for '%s': %s", query, e)
        return None


def _fetch_pexels(query: str, cache_dir: Path, hash_key: str) -> dict | None:
    if not PEXELS_API_KEY:
        return None
    try:
        resp = requests.get(
            f"{PEXELS_API}/search",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": PEXELS_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        photos = data.get("photos", [])
        if not photos:
            return None

        photo = photos[0]
        img_url = photo["src"]["large"]
        img_resp = requests.get(img_url, timeout=15)
        img_resp.raise_for_status()

        photographer = photo.get("photographer", "Unknown")
        photographer_url = photo.get("photographer_url", "https://www.pexels.com")
        meta = {
            "url": f"/photo-cache/{hash_key}.jpg",
            "alt": query,
            "attribution": f'Photo by <a href="{photographer_url}">{photographer}</a> on <a href="https://www.pexels.com">Pexels</a>',
            "source": "pexels",
        }
        _save_cache(cache_dir, hash_key, meta, img_resp.content)
        return meta
    except Exception as e:
        logger.warning("Pexels fetch failed for '%s': %s", query, e)
        return None


def fetch_photos(photo_list: list, cache_dir: Path) -> dict:
    """
    Returns {position: {url, alt, attribution}} for each photo.
    Gracefully skips failures — caller never sees exceptions.
    """
    if not photo_list:
        return {}

    results = {}
    for photo in photo_list:
        query = photo.get("query", "")
        position = photo.get("position", "after-intro")
        if not query:
            continue

        hash_key = _query_hash(query)

        cached = _load_cache(cache_dir, hash_key)
        if cached:
            results[position] = cached
            continue

        meta = _fetch_unsplash(query, cache_dir, hash_key)
        if meta is None:
            meta = _fetch_pexels(query, cache_dir, hash_key)
        if meta is not None:
            results[position] = meta
        else:
            logger.warning("No photo found for query '%s' at position '%s'", query, position)

    return results
