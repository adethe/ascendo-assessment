import os
import json
from typing import Any, Dict, List
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


PLANNER_SYSTEM = """
You are a supervisor planner for a data pipeline.

Goal:
Given a conference website URL, produce an execution plan to:
1) Extract a pre-conference company list using sponsor/logo sources.
2) Classify each company for ICP fit.

Constraints:
- Allowed tools (steps) are fixed and must be used exactly from this set:
  - scrape_homepage
  - crawl_sponsor_pages
  - validate_icp
  - export_csv

- The output MUST be valid JSON with this schema:

{
  "plan": [
    {"tool": "scrape_homepage", "params": {"url": "..."}, "why": "short"},
    {"tool": "crawl_sponsor_pages", "params": {"url": "...", "cap": 200}, "why": "short"},
    {"tool": "validate_icp", "params": {"batch_size": 10}, "why": "short"},
    {"tool": "export_csv", "params": {"out_csv": "companies_validated.csv"}, "why": "short"}
  ]
}

Notes:
- Always include validate_icp and export_csv.
- Include crawl_sponsor_pages if sponsor links likely exist or if coverage is important.
- Keep params minimal.
Return JSON only.
"""


def make_plan(url: str, out_csv: str, model: str) -> List[Dict[str, Any]]:
    llm = ChatGoogleGenerativeAI(
        model=model,
        temperature=0.2,
        model_kwargs={"response_mime_type": "application/json"},
    )

    user_prompt = {
        "url": url,
        "out_csv": out_csv,
        "hint": "This is a conference site. Prefer logo and sponsor page extraction.",
    }

    resp = llm.invoke(PLANNER_SYSTEM + "\n\nInput:\n" + json.dumps(user_prompt))
    text = resp.content if hasattr(resp, "content") else str(resp)

    obj = json.loads(text)
    plan = obj.get("plan", [])

    if not isinstance(plan, list) or not plan:
        raise ValueError("Planner returned empty or invalid plan")

    return plan