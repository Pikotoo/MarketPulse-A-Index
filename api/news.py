"""
新闻聚合 — 文件缓存 + RSS抓取 + 手动更新 + 利好/利空分类

存储: H:\MarketPulse\data\news_cache.json
更新: py -3.11 scripts/update_news.py
分类: 关键词匹配 + DeepSeek AI 兜底
"""

import sys
import json
import hashlib
import logging
import os
from pathlib import Path
from datetime import date, datetime
from typing import Optional

_MP_ROOT = Path(__file__).parent.parent
if str(_MP_ROOT) not in sys.path:
    sys.path.insert(0, str(_MP_ROOT))

from config import DATA_DIR

NEWS_FILE = DATA_DIR / "news_cache.json"
_log = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# 利好/利空 关键词库
# ═══════════════════════════════════════════
BULLISH_KEYWORDS = [
    '利好', '大涨', '飙升', '突破', '创新高', '牛市', '反弹', '回暖',
    '降息', '宽松', '放水', '刺激', '减税', '补贴', '扶持', '降准',
    '通过', '批准', '落地', '开闸', '放宽', '松绑', '利好政策',
    '盈利', '超预期', '业绩', '分红', '回购', '增持',
    '抄底', '资金流入', '外资', '北向资金', '爆买', '流入',
    '止跌', '企稳', '见底', '反转', '新政', '支持',
    'upgrade', 'bullish', 'rally', 'surge', 'breakthrough', 'rate cut',
    'approve', 'passed', 'stimulus', 'buyback', 'inflow',
]
BEARISH_KEYWORDS = [
    '利空', '暴跌', '崩盘', '熔断', '跌停', '熊市', '跳水', '跌破',
    '加息', '收紧', '缩表', '去杠杆', '监管', '打压', '整顿', '蒸发', '通胀',
    '否决', '搁置', '叫停', '退市', '清盘', '违约', '暴雷',
    '亏损', '下滑', '不及预期', '预警', '减持', '套现',
    '抛售', '资金流出', '撤离', '外资流出', '流出',
    '地缘', '冲突', '制裁', '关税', '贸易战', '新规',
    '量子', '破解', '威胁', '恐慌', '打击',
    'downgrade', 'bearish', 'crash', 'plunge', 'selloff', 'rate hike',
    'rejected', 'blocked', 'investigation', 'crackdown', 'outflow',
]

# ═══════════════════════════════════════════
# RSS 源配置
# ═══════════════════════════════════════════
RSS_FEEDS = [
    {
        "name": "36氪",
        "url": "https://36kr.com/feed",
        "category": "科技财经",
        "enabled": True,
    },
    {
        "name": "财联社电报",
        "url": "https://www.cls.cn/telegraph",
        "category": "A股",
        "enabled": False,  # HTML页面，需专用解析器，暂禁用
    },
    {
        "name": "华尔街见闻",
        "url": "https://wallstreetcn.com/news/global",
        "category": "宏观",
        "enabled": False,  # 需JS渲染，暂禁用
    },
    # 更多 RSS 源可在下面添加。格式：
    # {"name": "源名称", "url": "RSS地址", "category": "分类", "enabled": True},
    # 注意：国内财经网站大多已停止提供 RSS，可通过 scripts/update_news.py 手动更新
]


def classify_sentiment(title: str, use_ai: bool = True) -> str:
    """
    判断新闻标题是利好/利空/中性
    先关键词匹配，不确定时可选 DeepSeek AI 分类
    """
    title_lower = title.lower()

    # 1. 关键词匹配（单侧命中 ≥1 即可，需对方为 0）
    bull_hits = sum(1 for kw in BULLISH_KEYWORDS if kw.lower() in title_lower)
    bear_hits = sum(1 for kw in BEARISH_KEYWORDS if kw.lower() in title_lower)

    if bull_hits >= 1 and bear_hits == 0:
        return '利好'
    elif bear_hits >= 1 and bull_hits == 0:
        return '利空'
    elif bull_hits == 0 and bear_hits == 0:
        return '中性'

    # 2. 冲突或模糊 → AI 兜底
    if use_ai:
        try:
            ai_result = _ai_classify(title)
            if ai_result:
                return ai_result
        except Exception:
            pass

    # 3. 最终裁决：多者胜
    if bull_hits > bear_hits:
        return '利好'
    elif bear_hits > bull_hits:
        return '利空'
    return '中性'


def _ai_classify(title: str) -> Optional[str]:
    """用 DeepSeek 判断单条新闻情绪"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        try:
            from config import DEEPSEEK_API_KEY
            api_key = DEEPSEEK_API_KEY
        except ImportError:
            pass
    if not api_key:
        return None

    import requests
    prompt = (
        f'判断这条财经新闻对A股/加密货币市场是利好、利空还是中性。'
        f'只回复一个词：利好、利空、或中性。\n\n标题：{title}'
    )
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 10, "temperature": 0,
            },
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"].strip()
        if '利好' in result: return '利好'
        if '利空' in result: return '利空'
        return '中性'
    except Exception:
        return None


def _read_cache() -> dict:
    """读取新闻缓存"""
    if NEWS_FILE.exists():
        try:
            return json.loads(NEWS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"updated": None, "articles": []}


def _write_cache(data: dict):
    """写入新闻缓存"""
    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_articles(articles: list[dict]) -> int:
    """
    批量添加新闻（按 URL 去重）
    每篇文章格式: {"title": "...", "source": "...", "url": "...", "category": "..."}
    """
    cache = _read_cache()
    existing_urls = {a["url"] for a in cache["articles"]}
    added = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    for a in articles:
        url = a.get("url", "")
        if not url or url in existing_urls:
            continue
        title = a.get("title", "")
        sentiment = a.get("sentiment") or classify_sentiment(title)
        cache["articles"].insert(0, {
            "title": title,
            "source": a.get("source", ""),
            "category": a.get("category", ""),
            "url": url,
            "published": a.get("published", now),
            "added_at": now,
            "sentiment": sentiment,
        })
        existing_urls.add(url)
        added += 1

    # 最多保留 500 条
    cache["articles"] = cache["articles"][:500]
    cache["updated"] = now
    _write_cache(cache)
    return added


def get_latest_news(limit: int = 15, category: str = None, sentiment: str = None) -> list[dict]:
    """获取最新新闻，支持按分类和情绪筛选"""
    cache = _read_cache()
    articles = cache["articles"]
    if category:
        articles = [a for a in articles if a.get("category") == category]
    if sentiment:
        articles = [a for a in articles if a.get("sentiment") == sentiment]
    return articles[:limit]


def news_stats() -> dict:
    """缓存统计，含情绪分布"""
    cache = _read_cache()
    sources = {}
    sentiments = {'利好': 0, '利空': 0, '中性': 0}
    for a in cache["articles"]:
        s = a.get("source", "未知")
        sources[s] = sources.get(s, 0) + 1
        sentiments[a.get("sentiment", "中性")] = sentiments.get(a.get("sentiment", "中性"), 0) + 1
    return {
        "total_cached": len(cache["articles"]),
        "last_updated": cache.get("updated"),
        "by_source": [{"source": k, "count": v} for k, v in sources.items()],
        "by_sentiment": sentiments,
    }


def fetch_rss_feed(feed_url: str, source_name: str, category: str = "",
                   timeout: int = 15, max_articles: int = 10) -> list[dict]:
    """
    从单个 RSS/Atom Feed 抓取文章

    Args:
        feed_url: RSS/Atom feed URL
        source_name: 来源名称（用于去重和展示）
        category: 分类标签
        timeout: 请求超时秒数
        max_articles: 最多返回文章数

    Returns:
        list of {"title", "source", "url", "category", "published"}
    """
    try:
        import feedparser
        import ssl
    except ImportError:
        _log.warning("feedparser not installed, RSS fetch disabled")
        return []

    if hasattr(ssl, "_create_unverified_context"):
        ssl_context = ssl._create_unverified_context()
    else:
        ssl_context = None

    try:
        feed = feedparser.parse(feed_url, agent="MarketPulse-A-Index/2.1 RSS Reader")
    except Exception:
        # Retry with SSL context
        try:
            feed = feedparser.parse(feed_url, agent="MarketPulse-A-Index/2.1 RSS Reader")
        except Exception as e:
            _log.warning(f"RSS parse failed for {source_name}: {e}")
            return []

    if feed.bozo and not feed.entries:
        _log.warning(f"RSS {source_name}: parse error (bozo), no entries")
        return []

    articles = []
    for entry in feed.entries[:max_articles]:
        url = entry.get("link", "")
        if not url:
            continue

        title = entry.get("title", "").strip()
        if not title:
            continue

        # 提取发布时间
        published = ""
        for field in ("published", "updated", "created"):
            if entry.get(field):
                try:
                    from email.utils import parsedate_to_datetime
                    published = parsedate_to_datetime(entry[field]).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    try:
                        published = entry[field][:19]
                    except Exception:
                        pass
                break
        if not published:
            published = datetime.now().strftime("%Y-%m-%d %H:%M")

        articles.append({
            "title": title[:200],  # 截断过长标题
            "source": source_name,
            "url": url,
            "category": category,
            "published": published,
        })

    return articles


def refresh_from_rss() -> dict:
    """
    从所有启用的 RSS 源抓取新闻，去重后写入缓存

    Returns:
        {"added": N, "skipped": M, "errors": [...], "sources_scanned": N}
    """
    all_articles = []
    errors = []
    sources_scanned = 0

    for feed_cfg in RSS_FEEDS:
        if not feed_cfg.get("enabled", False):
            continue
        sources_scanned += 1
        try:
            articles = fetch_rss_feed(
                feed_url=feed_cfg["url"],
                source_name=feed_cfg["name"],
                category=feed_cfg.get("category", ""),
            )
            all_articles.extend(articles)
            _log.info(f"RSS {feed_cfg['name']}: {len(articles)} articles fetched")
        except Exception as e:
            errors.append(f"{feed_cfg['name']}: {str(e)[:100]}")
            _log.error(f"RSS {feed_cfg['name']} failed: {e}")

    if not all_articles:
        return {
            "added": 0, "skipped": 0,
            "errors": errors,
            "sources_scanned": sources_scanned,
            "message": "没有启用的RSS源或所有源抓取失败",
        }

    # 去重写入
    cache = _read_cache()
    existing_urls = {a["url"] for a in cache["articles"]}
    added = 0
    skipped = 0

    for a in all_articles:
        if a["url"] in existing_urls:
            skipped += 1
            continue
        cache["articles"].insert(0, {
            "title": a["title"],
            "source": a["source"],
            "category": a["category"],
            "url": a["url"],
            "published": a["published"],
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        existing_urls.add(a["url"])
        added += 1

    cache["articles"] = cache["articles"][:500]
    cache["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _write_cache(cache)

    return {
        "added": added,
        "skipped": skipped,
        "errors": errors,
        "sources_scanned": sources_scanned,
        "total_cached": len(cache["articles"]),
        "message": f"新增 {added} 条，跳过 {skipped} 条重复",
    }


# ═══════════════════════════════════════════
# 新浪财经 7×24 滚动新闻抓取器
# ═══════════════════════════════════════════
SINA_ROLL_API = "https://feed.mix.sina.com.cn/api/roll/get"
SINA_LID_A_SHARE = 2509  # A股+全球财经混合频道


def fetch_sina_7x24(lid: int = SINA_LID_A_SHARE, num: int = 30,
                    timeout: int = 15) -> list[dict]:
    """
    从新浪财经 7×24 滚动新闻 API 抓取最新新闻

    Args:
        lid: 频道ID，2509=A股+全球财经
        num: 抓取条数
        timeout: 超时秒数

    Returns:
        list of {title, source, url, category, published}
    """
    import requests

    params = {
        "pageid": 153,
        "lid": lid,
        "k": "",
        "num": min(num, 100),
        "page": 1,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }

    try:
        resp = requests.get(SINA_ROLL_API, params=params, headers=headers,
                           timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        _log.error(f"新浪7x24 API请求失败: {e}")
        return []

    if data.get("result", {}).get("status", {}).get("code") != 0:
        _log.error(f"新浪7x24 API返回错误: {data.get('result', {}).get('status', {})}")
        return []

    articles = []
    for item in data.get("result", {}).get("data", []):
        title = item.get("title", "").strip()
        if not title:
            continue

        url = item.get("url", "")
        if not url:
            continue

        # 转换 Unix 时间戳
        ctime = item.get("ctime", "")
        try:
            from datetime import datetime as dt
            published = dt.fromtimestamp(int(ctime)).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError, OSError):
            published = dt.now().strftime("%Y-%m-%d %H:%M")

        source = item.get("media_name", "新浪财经")
        intro = item.get("intro", "")

        # 分类
        sentiment = classify_sentiment(title + " " + intro[:100])

        articles.append({
            "title": title[:200],
            "source": source,
            "url": url,
            "category": "A股",
            "published": published,
            "sentiment": sentiment,
        })

    return articles


def refresh_from_sina(lid: int = SINA_LID_A_SHARE, num: int = 30) -> dict:
    """
    从新浪财经抓取 → 分类 → 写入缓存

    Returns:
        {added, skipped, sources_scanned, total_cached, message}
    """
    articles = fetch_sina_7x24(lid=lid, num=num)
    if not articles:
        return {
            "added": 0, "skipped": 0, "sources_scanned": 1,
            "total_cached": 0, "message": "新浪7x24 API抓取失败",
        }

    cache = _read_cache()
    existing_urls = {a["url"] for a in cache["articles"]}
    added = 0
    skipped = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    for a in articles:
        if a["url"] in existing_urls:
            skipped += 1
            continue
        cache["articles"].insert(0, {
            "title": a["title"],
            "source": a["source"],
            "category": a.get("category", ""),
            "url": a["url"],
            "published": a["published"],
            "added_at": now,
            "sentiment": a.get("sentiment", classify_sentiment(a["title"])),
        })
        existing_urls.add(a["url"])
        added += 1

    cache["articles"] = cache["articles"][:500]
    cache["updated"] = now
    _write_cache(cache)

    return {
        "added": added,
        "skipped": skipped,
        "sources_scanned": 1,
        "total_cached": len(cache["articles"]),
        "message": f"新浪7x24: 新增 {added} 条，跳过 {skipped} 条重复",
    }
