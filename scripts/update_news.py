"""
新闻更新脚本 — 手动添加/更新新闻缓存

用法:
  py -3.11 scripts/update_news.py --seed     # 写入种子数据（首次使用）
  py -3.11 scripts/update_news.py --add       # 从文件读取新增新闻
  py -3.11 scripts/update_news.py --stats     # 查看缓存统计
"""

import sys
import json
from pathlib import Path

_MP_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_MP_ROOT))

from api.news import add_articles, get_latest_news, news_stats

# 种子新闻 — 来源于公开财经资讯
SEED_NEWS = [
    {
        "title": "证监会：全面深化资本市场改革 支持科技创新企业发展",
        "source": "证监会", "category": "政策监管",
        "url": "http://www.csrc.gov.cn/#1",
    },
    {
        "title": "央行开展逆回购操作 维护银行体系流动性合理充裕",
        "source": "央行", "category": "货币政策",
        "url": "http://www.pbc.gov.cn/#1",
    },
    {
        "title": "6月PMI数据公布 制造业景气度边际改善",
        "source": "统计局", "category": "宏观经济",
        "url": "http://www.stats.gov.cn/#1",
    },
    {
        "title": "沪深港通北向资金连续净流入 外资看好A股长期配置价值",
        "source": "市场动态", "category": "资金流向",
        "url": "https://www.sse.com.cn/#1",
    },
    {
        "title": "两市融资余额突破2.9万亿元 杠杆资金入场意愿增强",
        "source": "市场动态", "category": "两融动态",
        "url": "https://www.sse.com.cn/#2",
    },
    {
        "title": "A股市场估值处历史中低位 权益资产配置性价比凸显",
        "source": "市场动态", "category": "估值分析",
        "url": "https://www.sse.com.cn/#3",
    },
    {
        "title": "国务院常务会议：加大宏观政策调控力度 着力扩大内需",
        "source": "国务院", "category": "政策监管",
        "url": "http://www.gov.cn/#1",
    },
    {
        "title": "人民币汇率在合理均衡水平上保持基本稳定",
        "source": "央行", "category": "汇率动态",
        "url": "http://www.pbc.gov.cn/#2",
    },
    {
        "title": "人工智能产业政策密集出台 国产大模型应用加速落地",
        "source": "产业资讯", "category": "科技产业",
        "url": "https://www.miit.gov.cn/#1",
    },
    {
        "title": "中报季来临 上市公司业绩预告整体向好",
        "source": "市场动态", "category": "市场动态",
        "url": "https://www.sse.com.cn/#4",
    },
]


def cmd_seed():
    """写入种子数据"""
    added = add_articles(SEED_NEWS)
    print(f"已添加 {added} 条种子新闻")
    stats = news_stats()
    print(f"缓存总数: {stats['total_cached']} 条")
    for s in stats["by_source"]:
        print(f"  {s['source']}: {s['count']} 条")


def cmd_add(filepath: str = None):
    """从 JSON 文件读取新闻并添加"""
    if filepath is None:
        filepath = _MP_ROOT / "data" / "news_incoming.json"
    path = Path(filepath)
    if not path.exists():
        print(f"文件不存在: {path}")
        print("格式: [{\"title\": \"...\", \"source\": \"...\", \"url\": \"...\", \"category\": \"...\"}, ...]")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("错误: 文件应为 JSON 数组")
        return
    added = add_articles(data)
    print(f"已添加 {added} 条新闻（总 {news_stats()['total_cached']} 条）")


def cmd_stats():
    """查看缓存状态"""
    stats = news_stats()
    print(f"新闻缓存统计:")
    print(f"  总条数: {stats['total_cached']}")
    print(f"  最近更新: {stats['last_updated']}")
    print(f"  来源分布:")
    for s in stats["by_source"]:
        print(f"    [{s['source']}] {s['count']} 条")
    print()
    for a in get_latest_news(5):
        print(f"  [{a['source']}] {a['title'][:50]}")


def cmd_rss():
    """从 RSS 源抓取新闻"""
    from api.news import refresh_from_rss
    result = refresh_from_rss()
    print(f"RSS 刷新完成:")
    print(f"  扫描源数: {result['sources_scanned']}")
    print(f"  新增: {result['added']} 条")
    print(f"  跳过(重复): {result['skipped']} 条")
    if result["errors"]:
        print(f"  错误:")
        for e in result["errors"]:
            print(f"    - {e}")
    print(f"  缓存总数: {result['total_cached']} 条")


def cmd_sina(num: int = 20):
    """从新浪财经 7×24 滚动新闻抓取"""
    from api.news import refresh_from_sina
    result = refresh_from_sina(num=num)
    print(f"新浪7x24 刷新完成:")
    print(f"  新增: {result['added']} 条")
    print(f"  跳过(重复): {result['skipped']} 条")
    if result.get("errors"):
        for e in result["errors"]:
            print(f"    - {e}")
    print(f"  缓存总数: {result['total_cached']} 条")

    # 显示情绪分布
    from api.news import news_stats
    stats = news_stats()
    s = stats["by_sentiment"]
    print(f"  情绪分布: 🟢利好{s.get('利好',0)} 🔴利空{s.get('利空',0)} ⚪中性{s.get('中性',0)}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="MarketPulse 新闻更新")
    p.add_argument("--seed", action="store_true", help="写入种子数据")
    p.add_argument("--add", nargs="?", const=True, help="从 JSON 文件添加新闻")
    p.add_argument("--rss", action="store_true", help="从 RSS 源抓取新闻")
    p.add_argument("--sina", type=int, nargs="?", const=20, help="从新浪7x24抓取（默认20条）")
    p.add_argument("--stats", action="store_true", help="查看缓存统计")
    args = p.parse_args()

    if args.seed:
        cmd_seed()
    elif args.add:
        cmd_add(args.add if isinstance(args.add, str) else None)
    elif args.rss:
        cmd_rss()
    elif args.sina is not None:
        cmd_sina(num=args.sina)
    elif args.stats:
        cmd_stats()
    else:
        cmd_stats()
