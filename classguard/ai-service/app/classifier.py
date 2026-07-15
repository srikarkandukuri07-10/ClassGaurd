import re
import os
import httpx
import json
from typing import Optional

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

STUDYING_KEYWORDS = {
    "visual studio code", "vscode", "code", "ide", "pycharm", "intellij",
    "eclipse", "netbeans", "clion", "xcode", "android studio",
    "terminal", "cmd", "powershell", "wsl", "bash",
    "jupyter", "notebook", "colab", "kaggle",
    "leetcode", "hackerrank", "codeforces", "geeksforgeeks",
    "stackoverflow", "github", "gitlab", "bitbucket",
    "chatgpt", "claude", "bard", "gemini", "copilot",
    "postgresql", "mysql", "mongodb", "sqlite", "database",
    "docker", "kubernetes", "jenkins", "nginx",
    "react", "angular", "vue", "node", "django", "flask",
    "python", "java", "javascript", "typescript", "rust", "go",
    "tensorflow", "pytorch", "sklearn", "pandas", "numpy",
    "pdf", "document", "research", "paper", "textbook",
    "moodle", "blackboard", "canvas", "lms",
    "nptel", "coursera", "udemy", "edx",
    "dbms", "operating system", "computer network", "dsa",
    "data structure", "algorithm", "oop", "compiler",
}

OFF_TASK_KEYWORDS = {
    "netflix", "youtube", "prime video", "hotstar", "disney+",
    "instagram", "facebook", "twitter", "x.com", "reddit",
    "snapchat", "whatsapp", "telegram", "discord",
    "tiktok", "instagram stories", "reels", "shorts",
    "amazon", "flipkart", "myntra", "ajio", "meesho",
    "zomato", "swiggy", "uber eats",
    "spotify", "gaana", "wynk", "jiosaavn",
    "game", "gaming", "minecraft", "pubg", "fortnite",
    "cricket", "ipl", "football", "sports",
    "movie", "web series", "tv show", "anime",
    "pinterest", "quora", "9gag", "imgur",
    "comedy", "memes", "entertainment",
}

SUSPICIOUS_KEYWORDS = {
    "vpn", "proxy", "tor", "incognito", "private browsing",
    "task manager", "process hacker", "process explorer",
    "screen capture blocker", "anti screen capture",
}

STUDYING_YOUTUBE_PATTERNS = [
    r"lecture", r"tutorial", r"course", r"lesson",
    r"dbms", r"os ", r"computer network", r"dsa",
    r"algorithm", r"data structure", r"programming",
    r"machine learning", r"deep learning", r"ai ",
    r"cloud computing", r"cyber security",
    r"software engineering", r"web development",
]


class ScreenClassifier:
    async def classify(
        self,
        image_b64: Optional[str] = None,
        window_title: Optional[str] = None,
        browser_tabs: Optional[list[str]] = None,
    ) -> dict:
        # 1. Try Gemini Vision first if image is provided and key is present
        if image_b64 and GEMINI_API_KEY:
            gemini_result = await self._classify_image_with_gemini(image_b64, window_title)
            if gemini_result:
                return gemini_result

        # 2. Local Fallback Heuristics
        reasons = []
        title_lower = (window_title or "").lower()
        all_tabs_lower = [t.lower() for t in (browser_tabs or [])]

        if self._is_studying_activity(title_lower, all_tabs_lower):
            if window_title:
                reasons.append(window_title)
            return {"status": "studying", "reason": "; ".join(reasons) or "Focus task", "confidence": 0.85}

        if self._is_suspicious_activity(title_lower, all_tabs_lower):
            if window_title:
                reasons.append(f"Suspicious activity: {window_title}")
            return {"status": "suspicious", "reason": "; ".join(reasons), "confidence": 0.8}

        if self._is_off_task_activity(title_lower, all_tabs_lower):
            if window_title:
                reasons.append(window_title)
            return {"status": "off-task", "reason": "; ".join(reasons), "confidence": 0.9}

        return {"status": "studying", "reason": "No clear off-task indicators", "confidence": 0.5}

    def _is_studying_activity(self, title: str, tabs: list[str]) -> bool:
        texts = [title] + tabs
        for t in texts:
            for kw in STUDYING_KEYWORDS:
                if kw in t:
                    return True
            for pat in STUDYING_YOUTUBE_PATTERNS:
                if re.search(pat, t):
                    return True
        return False

    def _is_off_task_activity(self, title: str, tabs: list[str]) -> bool:
        texts = [title] + tabs
        for t in texts:
            for kw in OFF_TASK_KEYWORDS:
                if kw in t:
                    return True
        return False

    def _is_suspicious_activity(self, title: str, tabs: list[str]) -> bool:
        texts = [title] + tabs
        for t in texts:
            for kw in SUSPICIOUS_KEYWORDS:
                if kw in t:
                    return True
        return False

    async def _classify_image_with_gemini(self, image_b64: str, window_title: Optional[str] = None) -> Optional[dict]:
        img_data = image_b64
        if "," in img_data:
            img_data = img_data.split(",")[1]

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

        prompt = (
            "Analyze this student's desktop screenshot. Classify their activity into one of these categories:\n"
            "- studying (coding in IDE, taking notes, reading textbook, reading research papers, watching academic lectures/tutorials, etc.)\n"
            "- suspicious (VPN, proxy, private/incognito browsing, process management/hacking tools, anti-monitoring tools, etc.)\n"
            "- off-task (games, streaming movies, chatting/messaging apps, social media scrolling, entertainment/gaming videos, e-commerce shopping, etc.)\n\n"
            "Your output must be a valid, parseable JSON object in this exact format:\n"
            "{\n"
            "  \"status\": \"studying\" | \"suspicious\" | \"off-task\",\n"
            "  \"reason\": \"A short description of what they are doing (e.g. Browsing Instagram, Watching YouTube, Coding in VS Code)\",\n"
            "  \"confidence\": 0.0 to 1.0\n"
            "}\n"
            "Do not include any markdown, backticks, comments, or extra text. Output ONLY the raw JSON."
        )
        if window_title:
            prompt += f"\n\nActive Window Title reported by system: {window_title}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": img_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    resp_json = resp.json()
                    text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    data = json.loads(text.strip())
                    if "status" in data and "reason" in data:
                        return {
                            "status": data["status"],
                            "reason": data["reason"],
                            "confidence": float(data.get("confidence", 0.95))
                        }
        except Exception as e:
            print("Gemini Vision API call failed:", e)
        return None
