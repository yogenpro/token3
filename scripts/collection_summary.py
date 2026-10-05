"""Emit a bounded GitHub Actions summary without raw source bodies or secrets."""
import json
from pathlib import Path
from .normalize import ROOT


def main():
    data = ROOT / "data"
    status = json.loads((data / "status.json").read_text())
    inventory = json.loads((data / "provider_inventory.json").read_text())
    rows = {p["id"]:p for p in inventory["providers"]}
    print("## Official pricing collection")
    print("Last recorded attempt: `{}`".format(status["last_run_at"]))
    print("\n| Provider | Health | Inventory records | Source | Fallback | Archive reference |")
    print("|---|---|---:|---|---|---|")
    def cell(value):
        return str(value or "—").replace("|", "\\|").replace("\n", " ")[:250]
    for provider in status["providers"]:
        row = rows.get(provider["id"], {})
        reference = row.get("archive_reference") or {}
        print("| {} | {} | {} | {} | {} | {} |".format(*map(cell, [provider["name"], provider["state"],
              row.get("record_count"), provider.get("source_kind"), provider.get("fallback_reason"), reference.get("state")])))
    print("\nPrice history is change-only. Check logs distinguish unchanged checks from failed checks.")
    print("Source-native formulas/units are preserved; inventory rows are not automatically comparable cost quotes.")
    print("Public raw responses expire after 7 days; authenticated model-catalog responses are not uploaded.")


if __name__ == "__main__":
    main()
