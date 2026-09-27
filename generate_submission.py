"""
Script to generate submission.jsonl from test_pairs.json using bot.compose.
"""

import json
from pathlib import Path
from bot import compose

def main():
    base_dir = Path(__file__).parent
    expanded_dir = base_dir / "dataset" / "expanded"
    
    # Load test pairs
    with open(expanded_dir / "test_pairs.json", encoding="utf-8") as f:
        test_pairs = json.load(f)["pairs"]

    # Load categories
    categories = {}
    for f in (expanded_dir / "categories").glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            cat = json.load(fp)
            categories[cat["slug"]] = cat

    # Load merchants
    merchants = {}
    for f in (expanded_dir / "merchants").glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            m = json.load(fp)
            merchants[m["merchant_id"]] = m

    # Load customers
    customers = {}
    for f in (expanded_dir / "customers").glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            c = json.load(fp)
            customers[c["customer_id"]] = c

    # Load triggers
    triggers = {}
    for f in (expanded_dir / "triggers").glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            t = json.load(fp)
            triggers[t["id"]] = t

    submission_path = base_dir / "submission.jsonl"
    print(f"Generating {len(test_pairs)} submissions to {submission_path}...")

    lines = []
    with open(submission_path, "w", encoding="utf-8") as out_f:
        for pair in test_pairs:
            test_id = pair["test_id"]
            trg_id = pair["trigger_id"]
            m_id = pair["merchant_id"]
            c_id = pair.get("customer_id")

            trigger = triggers[trg_id]
            merchant = merchants[m_id]
            customer = customers.get(c_id) if c_id else None
            cat_slug = merchant.get("category_slug", "dentists")
            category = categories.get(cat_slug, {"slug": cat_slug})

            res = compose(category, merchant, trigger, customer)

            record = {
                "test_id": test_id,
                "body": res["body"],
                "cta": res["cta"],
                "send_as": res["send_as"],
                "suppression_key": res["suppression_key"],
                "rationale": res["rationale"]
            }
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            lines.append(record)

    print(f"Successfully generated {len(lines)} lines in submission.jsonl.")
    for line in lines[:3]:
        print(f"[{line['test_id']}] ({line['send_as']}) {line['body'][:80]}... | CTA: {line['cta']}")

if __name__ == "__main__":
    main()
