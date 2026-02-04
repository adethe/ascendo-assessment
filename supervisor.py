import os
from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd
from dotenv import load_dotenv

from scraper import Company, scrape_companies
from validator_v2 import ValidatorAgentV2
from planner import make_plan

load_dotenv()


@dataclass
class RunResult:
    ok: bool
    output_csv: str
    rows: int
    notes: str


class Supervisor:

    def __init__(self, model: str | None = None):
        self.model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.validator = ValidatorAgentV2(model=self.model_name)

    def set_model(self, model: str):
        self.model_name = model
        self.validator = ValidatorAgentV2(model=self.model_name)

    def _default_plan(self, url: str, out_csv: str) -> List[Dict[str, Any]]:
        return [
            {"tool": "scrape_homepage", "params": {"url": url}, "why": "Get logo companies from homepage"},
            {"tool": "crawl_sponsor_pages", "params": {"url": url, "cap": 250}, "why": "Expand to all sponsors"},
            {"tool": "validate_icp", "params": {"batch_size": 10}, "why": "Classify ICP fit"},
            {"tool": "export_csv", "params": {"out_csv": out_csv}, "why": "Write deliverable CSV"},
        ]

    def _validate_plan(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        allowed = {"scrape_homepage", "crawl_sponsor_pages", "validate_icp", "export_csv"}
        tools = [step.get("tool") for step in plan]

        for t in tools:
            if t not in allowed:
                raise ValueError(f"Planner used invalid tool: {tools}")

        if "validate_icp" not in tools or "export_csv" not in tools:
            raise ValueError("Plan must include validate_icp and export_csv")

        return plan

    def run(self, url: str, out_csv: str = "companies_validated.csv") -> RunResult:
        print("[Supervisor] Planning with Gemini...")
        try:
            plan = make_plan(url=url, out_csv=out_csv, model=self.model_name)
            plan = self._validate_plan(plan)
        except Exception as e:
            print("[Supervisor] Planner failed, using default plan.")
            print("[Supervisor] Planner error:", repr(e))
            plan = self._default_plan(url, out_csv)

        print("[Supervisor] Plan:")
        for i, step in enumerate(plan, 1):
            print(f"  {i}. {step['tool']}  params={step.get('params', {})}  why={step.get('why','')}")

        companies = []
        validated_rows = []

        for step in plan:
            tool = step["tool"]
            params = step.get("params", {})

            if tool == "scrape_homepage":
                print("[Supervisor] Running ScraperAgent: homepage logos")
                companies = scrape_companies(params["url"])
                print(f"[ScraperAgent] extracted {len(companies)} companies")

            elif tool == "crawl_sponsor_pages":
                print("[Supervisor] Running ScraperAgent: sponsor page crawl")
                cap = int(params.get("cap", 250))
                companies = scrape_companies(params["url"], sponsor_link_cap=cap)
                print(f"[ScraperAgent] extracted {len(companies)} companies after sponsor crawl")

            elif tool == "validate_icp":
                print("[Supervisor] Running ValidatorAgent: ICP classification")
                batch_size = int(params.get("batch_size", 10))
                names = []
                for c in companies:
                    names.append(c.name)
                validated_rows = self.validator.validate(names, batch_size=batch_size)
                print(f"[ValidatorAgent] validated {len(validated_rows)} companies")

            elif tool == "export_csv":
                print("[Supervisor] Exporting CSV")
                out_path = params.get("out_csv", out_csv)

                scraper_data = []
                for c in companies:
                    scraper_data.append({
                        "company": c.name,
                        "source_url": c.source_url,
                        "source_hint": c.source_hint,
                    })
                sdf = pd.DataFrame(scraper_data)

                vdf = pd.DataFrame(validated_rows)
                out = sdf.merge(vdf, on="company", how="left")

                fit_rank = {"Yes": 0, "Maybe": 1, "No": 2}
                out["fit_rank"] = out["icp_fit"].map(fit_rank)
                out["fit_rank"] = out["fit_rank"].fillna(9)
                out = out.sort_values(["fit_rank", "confidence"], ascending=[True, False])
                out = out.drop(columns=["fit_rank"])

                out.to_csv(out_path, index=False)
                print(f"[Supervisor] Wrote {out_path} with {len(out)} rows")

                return RunResult(ok=True, output_csv=out_path, rows=len(out), notes="Plan executed successfully.")

        return RunResult(ok=False, output_csv=out_csv, rows=0, notes="Plan did not include export step.")