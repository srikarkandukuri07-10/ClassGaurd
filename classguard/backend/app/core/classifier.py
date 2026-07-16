import re
import httpx
import json
from typing import Optional
from app.core.config import settings

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
        api_key = settings.GEMINI_API_KEY
        title_lower = (window_title or "").lower()
        all_tabs_lower = [t.lower() for t in (browser_tabs or [])]

        print(f"\n--- [Classifier Start] Window: '{window_title}' ---")
        print(f"[Classifier Log] Gemini API Key present: {bool(api_key)}")

        # 1. Try Gemini Vision if image and key are present
        if image_b64 and api_key:
            print("[Classifier Log] Attempting Gemini Vision analysis...")
            gemini_result = await self._classify_image_with_gemini(image_b64, window_title, api_key)
            if gemini_result:
                print(f"[Classifier Log] Gemini Vision successful: {gemini_result}")
                return gemini_result
            else:
                print("[Classifier Log] Gemini Vision failed or returned null. Falling back to heuristics...")
        else:
            if not api_key:
                print("[Classifier Log] Gemini API Key is missing. Using heuristics fallback...")
            if not image_b64:
                print("[Classifier Log] No screenshot image provided. Using heuristics fallback...")

        # 2. Heuristics fallback
        print("[Classifier Log] Running Heuristics Classifier...")
        
        # Check off-task keywords first
        if self._is_off_task_activity(title_lower, all_tabs_lower):
            # Special case: check if YouTube has educational keywords
            if "youtube" in title_lower and any(pat in title_lower for pat in ["lecture", "tutorial", "course", "lesson", "dsa", "dbms", "os", "programming", "coding", "learn"]):
                result = {
                    "status": "studying",
                    "confidence": 0.85,
                    "activity": "Watching Educational YouTube Video",
                    "reason": "YouTube title indicates study/lecture content.",
                    "explanation": f"The student is watching a study-related video on YouTube: '{window_title}'."
                }
            else:
                result = {
                    "status": "off-task",
                    "confidence": 0.95,
                    "activity": f"Viewing Off-Task App/Website: '{window_title}'",
                    "reason": "Non-educational website/app keyword match.",
                    "explanation": f"Active window title '{window_title}' matches off-task keywords."
                }
            print(f"[Classifier Log] Heuristics matched off-task: {result}")
            return result

        # Check suspicious keywords
        if self._is_suspicious_activity(title_lower, all_tabs_lower):
            result = {
                "status": "suspicious",
                "confidence": 0.85,
                "activity": f"Using Suspicious Tool: '{window_title}'",
                "reason": "Suspicious application/window keyword match.",
                "explanation": f"The student is accessing process management or proxy tools: '{window_title}'."
            }
            print(f"[Classifier Log] Heuristics matched suspicious: {result}")
            return result

        # Check studying keywords
        if self._is_studying_activity(title_lower, all_tabs_lower):
            result = {
                "status": "studying",
                "confidence": 0.90,
                "activity": f"Academic/Coding Activity: '{window_title}'",
                "reason": "Educational tool or website keyword match.",
                "explanation": f"The student is active in a study-related window: '{window_title}'."
            }
            print(f"[Classifier Log] Heuristics matched studying: {result}")
            return result

        # Default fallback
        result = {
            "status": "studying",
            "confidence": 0.50,
            "activity": f"Active in: '{window_title}'",
            "reason": "No off-task or suspicious indicators found.",
            "explanation": f"No clear category matched for window '{window_title}'. Defaulting to studying."
        }
        print(f"[Classifier Log] Heuristics default response: {result}")
        return result

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

    async def _classify_image_with_gemini(
        self, image_b64: str, window_title: Optional[str], api_key: str
    ) -> Optional[dict]:
        img_data = image_b64
        if "," in img_data:
            img_data = img_data.split(",")[1]

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

        prompt = (
            "You are an intelligent classroom supervisor AI. Your task is to analyze the student's desktop screenshot and the active window title to classify their current activity.\n\n"
            "You must classify the activity into one of these three categories:\n"
            "1. STUDYING: Academic work, coding in IDEs (VS Code, PyCharm, IntelliJ, etc.), taking notes, reading textbooks/PDFs/research papers, watching educational/academic YouTube videos (e.g., lectures, tutorials, courses), using LMS platforms (Moodle, Canvas, Blackboard), or visiting academic websites.\n"
            "2. SUSPICIOUS: Random web browsing, unknown websites, excessive tab switching, use of VPNs/proxies/incognito tabs, process managers, or websites that cannot confidently be classified.\n"
            "3. OFF_TASK: Social media (Instagram, Facebook, Twitter/X, Reddit, Snapchat, Discord, WhatsApp Web), video streaming (Netflix, Prime Video, Disney+, entertainment/non-educational YouTube videos/shorts/reels), gaming, shopping, entertainment, or any other non-academic activities.\n\n"
            "Visual Guidelines:\n"
            "- Analyze the visual content of the screenshot. Look at the open windows, active tab, and browser address bar if visible.\n"
            "- If a website is open, look at the domain name in the address bar.\n"
            "- A platform like YouTube is STUDYING if a lecture/tutorial is clearly visible, but OFF_TASK if a music video, movie clip, shorts/reels, or general entertainment is active.\n\n"
            "Your output must be a valid, parseable JSON object in this exact format (do not include any markdown formatting, backticks, or text outside the JSON):\n"
            "{\n"
            "  \"status\": \"STUDYING\" | \"SUSPICIOUS\" | \"OFF_TASK\",\n"
            "  \"confidence\": 0.0 to 1.0,\n"
            "  \"activity\": \"A short, specific description of the activity (e.g., 'Browsing Instagram Reels', 'Watching YouTube Algorithms Lecture', 'Coding in VS Code')\",\n"
            "  \"reason\": \"A concise reason for this classification (e.g., 'Social media website detected on screen.')\",\n"
            "  \"explanation\": \"A detailed explanation of what the student is doing on screen and whether it relates to study.\"\n"
            "}"
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

        print(f"[Gemini Log] Request Payload prompt size: {len(prompt)} characters")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
                print(f"[Gemini Log] Response Status Code: {resp.status_code}")
                if resp.status_code == 200:
                    resp_json = resp.json()
                    text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"[Gemini Log] Raw response text: {text}")
                    data = json.loads(text.strip())
                    
                    status_raw = data.get("status", "studying").upper()
                    status_normalized = "studying"
                    if status_raw == "OFF_TASK":
                        status_normalized = "off-task"
                    elif status_raw == "SUSPICIOUS":
                        status_normalized = "suspicious"

                    return {
                        "status": status_normalized,
                        "confidence": float(data.get("confidence", 0.95)),
                        "activity": data.get("activity", "Active activity"),
                        "reason": data.get("reason", window_title or "Observation"),
                        "explanation": data.get("explanation", "")
                    }
                else:
                    print(f"[Gemini Log] Failed API call. Response content: {resp.text}")
        except Exception as e:
            print("[Gemini Log] Exception during API call:", e)
        return None
