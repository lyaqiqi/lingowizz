from flask import current_app
import requests
import json
import math
import re
import time
import logging

logging.basicConfig(level=logging.DEBUG)

class APIClient:
    def __init__(self):
        self.bilibili_base_url = "https://api.bilibili.com/x/web-interface/search/all/v2"

    def search_bilibili(self, search_query):
        """调用B站搜索API，提取视频数据"""
        current_app.logger.info(f"请求B站API: {self.bilibili_base_url}, {search_query}")
        params = {
            "keyword": search_query,
            "search_type": "video",
            "page": 1,
            "pagesize": 20
        }
        current_app.logger.info(f"请求B站API: {self.bilibili_base_url}, {params}")
        try:
            time.sleep(1)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            response = requests.get(self.bilibili_base_url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()

            video_list = []
            # 遍历 result 数组，找到 video 类型的结果
            for item in result.get("data", {}).get("result", []):
                if item.get("result_type") == "video":
                    # 提取 video 类型结果中的 data 数组（包含具体视频信息）
                    video_list.extend(item.get("data", []))

            return video_list

        except requests.RequestException as e:
            current_app.logger.error(f"B站搜索失败: {str(e)}")
            return []
        except Exception as e:
            current_app.logger.error(f"解析B站数据失败: {str(e)}")
            return []

class PromptGenerator:
    def generate_prompt(self, user_tags):
        """生成搜索词和推荐标签"""
        # 简单的搜索词生成逻辑
        search_query = " ".join(user_tags)
        
        # 基于用户标签生成推荐标签
        recommended_tags = []
        for tag in user_tags:
            if "sport" in tag.lower() or "运动" in tag:
                recommended_tags.extend(["运动", "健身", "训练"])
            elif "music" in tag.lower() or "音乐" in tag:
                recommended_tags.extend(["音乐", "歌曲", "演奏"])
            elif "cook" in tag.lower() or "烹饪" in tag:
                recommended_tags.extend(["烹饪", "美食", "料理"])
            else:
                recommended_tags.append(tag)
        
        return {
            "search_query": search_query,
            "tags": recommended_tags[:3]  # 限制为3个标签
        }

class RankingService:
    def rank_videos(self, user_intent, videos):
        """简单的视频排序逻辑"""
        # 这里可以实现更复杂的排序算法
        # 目前只是简单返回原列表
        return videos

class VideoSearchService:
    def __init__(self):
        self.api_client = APIClient()
        self.prompt_gen = PromptGenerator()
        self.ranking_service = RankingService()

    def get_recommended_videos(self, user_tags):
        """完整流程：生成搜索词 → 搜视频 → 排序 → 返回结果"""
        # 1. 生成搜索词和标签
        prompt_data = self.prompt_gen.generate_prompt(user_tags)
        search_query = prompt_data["search_query"]
        recommended_tags = prompt_data["tags"]

        # 2. 用户意图（用于排序）
        user_intent = " ".join(user_tags)

        # 3. 搜索视频
        raw_videos = self.api_client.search_bilibili(search_query)

        videos = []
        for video in raw_videos:
            try:
                # 提取关键视频信息
                cover_url = str(video.get("pic", ""))
                if cover_url.startswith("//"):
                    cover_url = "https:" + cover_url
                elif cover_url.startswith("http:"):
                    cover_url = cover_url.replace("http:", "https:")
                video_info = {
                    "id": str(video.get("bvid", "")),
                    "title": str(video.get("title", "")).replace("<em class=\"keyword\">", "").replace("</em>", ""),
                    "cover": cover_url,
                    "url": str(f"https://www.bilibili.com/video/{video.get('bvid', '')}"),
                    "duration": str(video.get("duration", "")),
                    "play_count": int(video.get("play", 0)),
                    "up": str(video.get("author", "")),
                    "tags": (str(video.get("tag", "")) or "").split(",") + recommended_tags[:2]
                }
                videos.append(video_info)
            except Exception as e:
                current_app.logger.warning(f"解析视频失败: {str(e)}")
                continue

        # 5. 排序视频
        ranked_videos = self.ranking_service.rank_videos(user_intent, videos)

        return {
            "search_query": search_query,
            "recommended_tags": recommended_tags,
            "videos": ranked_videos
        } 

class LearningVideoFinder:
    """
    对话中按情景检索英语学习短视频（B 站）。
    流程：补全检索词 → 搜索（带 buvid3 cookie，失败重试一次）→ 过滤 → 排序 → 缓存。
    与上面的 VideoSearchService 独立，不依赖 Flask 上下文。
    """
    HOME_URL = "https://www.bilibili.com/"
    SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    MAX_SECONDS = 15 * 60          # 只要短视频，方便课后练习
    MIN_PLAY = 500                 # 去掉过冷门的视频
    CACHE_TTL = 24 * 3600          # 同一检索词缓存一天，减少请求、降低风控概率
    LEARNING_HINTS = ("英语", "english", "口语")

    def __init__(self, session=None):
        self._session = session or requests.Session()
        self._has_cookie = False
        self._cache = {}

    def search(self, keywords: str, topic: str = "", limit: int = 3):
        query = self._build_query(keywords)
        cached = self._cache.get(query)
        if cached and time.time() - cached[0] < self.CACHE_TTL:
            return cached[1][:limit]
        try:
            raw = self._fetch(query)
        except Exception:
            self._has_cookie = False  # cookie 可能失效，重新获取后再试一次
            raw = self._fetch(query)
        videos = [v for v in (self._normalize(r) for r in raw) if v and self._keep(v)]
        videos.sort(key=lambda v: self._score(v, topic, query), reverse=True)
        self._cache[query] = (time.time(), videos)
        return videos[:limit]

    def _build_query(self, keywords: str) -> str:
        query = " ".join(keywords.split())
        if not any(h in query.lower() for h in ("英语", "english")):
            query += " 英语口语"
        return query

    def _fetch(self, query: str):
        if not self._has_cookie:
            self._session.get(self.HOME_URL, headers=self.HEADERS, timeout=10)
            self._has_cookie = True
        resp = self._session.get(self.SEARCH_URL, headers=self.HEADERS, timeout=10,
                                 params={"search_type": "video", "keyword": query, "page": 1})
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Bilibili search failed: {data.get('code')} {data.get('message')}")
        return (data.get("data") or {}).get("result") or []

    @staticmethod
    def _parse_duration(text: str) -> int:
        try:
            seconds = 0
            for part in str(text).split(":"):
                seconds = seconds * 60 + int(part)
            return seconds
        except ValueError:
            return 0

    def _normalize(self, item):
        bvid = item.get("bvid")
        if not bvid:
            return None
        cover = str(item.get("pic", ""))
        if cover.startswith("//"):
            cover = "https:" + cover
        duration = str(item.get("duration", ""))
        return {
            "title": re.sub(r"<[^>]+>", "", str(item.get("title", ""))),
            "url": f"https://www.bilibili.com/video/{bvid}",
            "cover": cover.replace("http:", "https:", 1) if cover.startswith("http:") else cover,
            "duration": duration,
            "seconds": self._parse_duration(duration),
            "play": int(item.get("play") or 0),
            "author": str(item.get("author", "")),
        }

    def _keep(self, video) -> bool:
        title = video["title"].lower()
        return (0 < video["seconds"] <= self.MAX_SECONDS and video["play"] >= self.MIN_PLAY
                and any(h in title for h in self.LEARNING_HINTS))

    @staticmethod
    def _score(video, topic: str, query: str) -> float:
        # 播放量（取对数）+ 标题与情景关键词的重合度
        title = video["title"].lower()
        terms = {t for t in query.lower().split() if t not in ("英语", "英语口语", "口语")}
        terms |= {w for w in re.findall(r"[a-z]+", topic.lower()) if len(w) > 2}
        overlap = sum(1 for t in terms if t in title)
        return math.log10(video["play"] + 1) + 1.5 * overlap
