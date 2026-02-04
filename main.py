import argparse
import os
from dotenv import load_dotenv

from supervisor import Supervisor

load_dotenv(override=True)

print("GOOGLE_API_KEY:", (os.getenv("GOOGLE_API_KEY") or ""))

def main():
    parser = argparse.ArgumentParser(description="Conference Company Scraper + ICP Validator")
    parser.add_argument("--url", required=True, help="Conference URL to scrape")
    parser.add_argument("--out", default="companies_validated.csv", help="Output CSV filename")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL"), help="Gemini model name (optional)")
    args = parser.parse_args()

    sup = Supervisor(model=args.model)
    result = sup.run(url=args.url, out_csv=args.out)

    print(f"OK={result.ok}")
    print(f"Output={result.output_csv}")
    print(f"Rows={result.rows}")
    print(result.notes)

if __name__ == "__main__":
    main()