# Ascendo.AI assessment

## Overview
This project pulls company names from a conference website and tries to understand which of those companies are a good fit for an AI Solutions / Field Service & Service Operations ICP. The final output is a CSV where companies are categorized, ranked by relevance, and given a short explanation for why they may or may not be a good fit.

The main goal isn’t perfect enrichment, but to quickly turn a long sponsor list into something more usable before an event.

---

## Architecture
The project follows a simple supervisor + agents setup.

- **Supervisor**  
  Runs the full pipeline end to end. It decides the order of steps (scrape → validate → export) and handles batching and retries.

- **Scraper Agent**  
  Deterministically extracts company names from the conference site. Most names come from sponsor/logo image `alt` text and sponsor pages. This part does not use an LLM.  
  BeautifulSoup is used by default, with an optional Playwright fallback for pages that load content dynamically.

- **Validator Agent**  
  Uses Gemini to classify companies in batches. It outputs structured JSON with category, ICP fit, confidence, evidence, and a short reason. Strict output formatting is enforced so results can be reliably written to CSV.

**Why this design**
- Keeps scraping and reasoning separate (less brittle, easier to debug)
- Makes it easy to add more agents later (ex: enrichment, CRM export, outreach suggestions)
- Uses LLMs only where they add value (classification and reasoning)

---

## ICP Definition
For this project, the ICP is focused on B2B companies involved in field service and service operations. This includes:

- Field Service Management (FSM), scheduling, dispatch, technician workflows  
- AI for service operations (diagnostics, predictive maintenance, service intelligence)  
- Remote assist and AR tools for technicians  
- IoT, telematics, fleet and asset monitoring platforms  
- Enterprise ERP / CRM / ITSM platforms with service-related modules  
- Consulting firms and system integrators focused on service transformation in asset-heavy industries  

---

## Output Columns
The final CSV (`companies_validated.csv`) includes:

- `company`
- `source_url`, `source_hint`
- `category`: FSM | AI Service | Remote Assist | Telematics/IoT | ERP/CRM | Consulting | Other
- `icp_fit`: Yes | Maybe | No
- `confidence`: 0–100 (rough confidence score)
- `evidence`: short phrase describing what the company does
- `reason`: one short sentence explaining the classification

## Setup
### 1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install
```
### 2. Environment variables
Create a `.env` file in the project root (.env.example file provided):
```env
GOOGLE_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
```

### 3. Running the pipeline
python main.py --url https://fieldserviceusa.wbresearch.com/ --out companies_validated.csv
