import pandas as pd
from scraper import scrape_companies

def main():
    url = "https://fieldserviceusa.wbresearch.com/"
    companies = scrape_companies(url)

    rows = []
    for c in companies:
        rows.append({
            "company": c.name,
            "source_url": c.source_url,
            "source_hint": c.source_hint
        })
    
    df = pd.DataFrame(rows)

    df = df.sort_values("company")
    df = df.reset_index(drop=True)
    out = "companies_raw.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {out} with {len(df)} rows")

if __name__ == "__main__":
    main()