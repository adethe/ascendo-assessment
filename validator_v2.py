import json
import re
from typing import Any, Dict, List

from langchain_google_genai import ChatGoogleGenerativeAI


ICP_TEXT = """
You are classifying companies for fit with an AI solutions / Field Service & Service Operations ideal customer profile (ICP).

Strong ICP fit (Yes):
- Field Service Management (FSM), dispatch/scheduling, service workflow automation
- Predictive maintenance, AI diagnostics, service intelligence/knowledge automation
- Remote assist / AR for technicians
- IoT / telematics / fleet or asset monitoring platforms used for service operations
- Enterprise platforms (ERP/CRM/ITSM) where service operations are a core module
- Consulting/SIs that implement service transformation for asset-heavy industries

Maybe:
- General enterprise software or consulting where relevance depends on service focus
- Hardware manufacturers where field service is a function but not the primary offering

No:
- Consumer-only brands, unrelated media/content, event names, people names
- Companies with unclear relevance from the name alone
"""

CATEGORIES = ["FSM", "AI Service", "Remote Assist", "Telematics/IoT", "ERP/CRM", "Consulting", "Other"]


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response")

    return json.loads(text[start:end + 1])

class ValidatorAgentV2:
    def __init__(self, model: str = "gemini-2.5-flash-lite"):
        self.llm = ChatGoogleGenerativeAI(
        model=model,
        temperature=0.1,
        model_kwargs={"response_mime_type": "application/json"}
        )


    def validate_batch(self, companies: List[str]) -> List[Dict[str, Any]]:
        prompt = f"""
        {ICP_TEXT}

        Return ONLY valid JSON with this schema:
        {{
        "results": [
            {{
            "company": "string",
            "category": "FSM|AI Service|Remote Assist|Telematics/IoT|ERP/CRM|Consulting|Other",
            "icp_fit": "Yes|Maybe|No",
            "confidence": 0-100,
            "evidence": "max 8 words",
            "reason": "max 20 words"
            }}
        ]
        }}

        Confidence calibration:
        - 90-100 only for widely known and clearly ICP (ServiceNow, Salesforce, SAP, Oracle, Geotab).
        - 70-89 for likely ICP but not certain from name alone.
        - 35-69 for uncertain, needs lookup.
        - 0-34 for not ICP.

        Companies:
        {json.dumps(companies)}
        """

        resp = self.llm.invoke(prompt).content
        obj = _extract_json(resp)

        results = obj.get("results", [])
        by_name = {}
        for r in results:
            if isinstance(r, dict):
                by_name[r.get("company", "").lower()] = r

        ordered = []
        for c in companies:
            r = by_name.get(c.lower())
            if not r:
                r = {
                    "company": c,
                    "category": "Other",
                    "icp_fit": "Maybe",
                    "confidence": 45,
                    "reason": "Insufficient info from name alone; likely needs quick lookup."
                }
            ordered.append(r)

        return ordered

    def validate(self, companies: List[str], batch_size: int = 10) -> List[Dict[str, Any]]:
        out = []
        for i in range(0, len(companies), batch_size):
            batch = companies[i:i + batch_size]
            try:
                out.extend(self.validate_batch(batch))
            except Exception as e:
                print("\nVALIDATOR FAILED. Batch:", batch)
                print("ERROR:", repr(e))

                for c in batch:
                    out.append({
                        "company": c,
                        "category": "Other",
                        "icp_fit": "Maybe",
                        "confidence": 40,
                        "reason": "Validator error; mark as Maybe pending manual review."
                    })
        return out