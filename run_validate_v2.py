import pandas as pd
from validator_v2 import ValidatorAgentV2

def main():
    df = pd.read_csv("companies_raw.csv")
    companies = df["company"].astype(str).tolist()

    agent = ValidatorAgentV2(model="gemini-2.5-flash-lite")
    validated = agent.validate(companies, batch_size=10)

    vdf = pd.DataFrame(validated)

    out = df.merge(vdf, on="company", how="left")

    rank = {"Yes": 0, "Maybe": 1, "No": 2}
    out["fit_rank"] = out["icp_fit"].map(rank)
    out["fit_rank"] = out["fit_rank"].fillna(9)
    out = out.sort_values(["fit_rank", "confidence"], ascending=[True, False])
    out = out.drop(columns=["fit_rank"])

    out_file = "companies_validated.csv"
    out.to_csv(out_file, index=False)
    print(f"Wrote {out_file} with {len(out)} rows")

if __name__ == "__main__":
    main()