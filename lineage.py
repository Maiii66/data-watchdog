# Map data sources to downstream systems and report affected targets.
LINEAGE = {
    "orders.csv": [
        "Revenue Dashboard",
        "Marketing Report",
        "Fraud Detection Model",
    ]
}


def who_is_affected(source: str):
    affected = LINEAGE.get(source)
    if affected:
        print("\nDownstream systems at risk:")
        for system in affected:
            print(f"  - {system}")
    else:
        print(f"\nNo downstream systems are affected by {source}.")
