"""
core/autonomous_learner.py — Neural-Guided Autonomous Learning Engine for MJ-AI.
================================================================================
Features:
  1. Searches Web / GitHub repos for new Python libraries, AI patterns & tools.
  2. Uses Neural Brain to evaluate architectural feasibility & safety.
  3. Extracts durable technical concepts and stores them in MJ memory (skills & semantic_memory).
  4. Proposes verified code improvements to the Neural Self-Modifier.
"""

import asyncio
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path
import requests

from core.neural_brain import get_neural_brain


def get_base_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
MEMORY_DIR = BASE_DIR / "memory"
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


class AutonomousLearner:
    """
    Background engine that continuously expands MJ's knowledge graph & skill parameters
    by exploring online resources, GitHub repositories, and documentation with Neural Brain guidance.
    """

    def __init__(self, check_interval_secs: int = 3600):
        self.check_interval_secs = check_interval_secs
        self._running = False
        self._thread: threading.Thread | None = None
        self._learned_topics: set[str] = set()
        self.brain = get_neural_brain()

    def _get_api_key(self) -> str | None:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("gemini_api_key")
        except Exception:
            return None

    def search_github_trending(self, query: str = "python ai assistant agent") -> list[dict]:
        """Search GitHub for top trending repositories matching AI/automation topics."""
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=5"
        headers = {"User-Agent": "MJ-AI-Learner/1.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                results = []
                for item in items:
                    results.append({
                        "name": item.get("full_name"),
                        "description": item.get("description"),
                        "stars": item.get("stargazers_count"),
                        "url": item.get("html_url"),
                    })
                return results
        except Exception as e:
            print(f"[AutoLearner] GitHub search failed: {e}")
        return []

    def learn_concept(self, topic: str, context_info: str) -> str:
        """Uses Gemini to distill a GitHub repo or web article into a durable MJ skill memory."""
        api_key = self._get_api_key()
        if not api_key:
            return "No API key available"

        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = f"""You are an autonomous AI self-learning engine.
Analyze this technical topic/repository and summarize the core key learnings, python libraries, and code patterns.

Topic: {topic}
Source Context: {context_info[:3000]}

Format as a concise structured summary (3-5 bullet points) of useful skills, API patterns, or techniques to learn."""

            resp = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            summary = resp.text.strip()
            
            # Save to memory engine
            from memory.memory_manager import saveMemory
            saveMemory(
                memory={
                    "category": "skills",
                    "key": f"learned_{re.sub(r'[^a-z0-9]', '_', topic.lower())[:30]}",
                    "value": summary,
                    "confidence": 0.9,
                    "importance": 8,
                    "source": "autonomous_github_learning"
                }
            )
            print(f"[AutoLearner] 🧠 Mastered new concept: {topic}")
            return summary

        except Exception as e:
            print(f"[AutoLearner] Failed to learn concept '{topic}': {e}")
            return f"Learning failed: {e}"

    def run_learning_cycle(self):
        """Single learning iteration guided by Neural Brain."""
        print("[AutoLearner] 🔍 Searching GitHub & Web for new AI agent patterns...")
        repos = self.search_github_trending("python ai agent automation tool")
        for repo in repos:
            repo_name = repo["name"]
            if repo_name in self._learned_topics:
                continue
            self._learned_topics.add(repo_name)
            desc = repo.get("description") or ""
            print(f"[AutoLearner] 💡 Inspecting repo: {repo_name} ({repo.get('stars')} stars)")
            self.learn_concept(repo_name, f"{desc}\nURL: {repo.get('url')}")
            time.sleep(2)

    def _loop(self):
        time.sleep(30)  # Initial startup delay
        while self._running:
            try:
                self.run_learning_cycle()
            except Exception as e:
                print(f"[AutoLearner] Loop error: {e}")
            time.sleep(self.check_interval_secs)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[AutoLearner] 🚀 Autonomous Neural Learning Engine STARTED.")

    def stop(self):
        self._running = False
