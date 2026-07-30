from pathlib import Path
from faker import Faker
import csv

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = DATA_DIR / "orders.csv"

# Generate a fake orders dataset and save it as CSV.
def generate_data(break_it=False):
    fake = Faker()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    rows = 200
    headers = ["order_id", "customer", "amount", "status", "city", "created_at"]
    if break_it:
        rows = 40
        headers = ["order_id", "amount", "status", "city", "created_at"]

    records = []
    for i in range(1, rows + 1):
        record = {
            "order_id": f"ORD{i:04d}",
            "customer": fake.name(),
            "amount": round(fake.pydecimal(left_digits=4, right_digits=2, positive=True), 2),
            "status": fake.random_element(elements=("completed", "pending", "cancelled", "returned")),
            "city": fake.city(),
            "created_at": fake.date_time_between(start_date='-30d', end_date='now').strftime('%Y-%m-%d %H:%M:%S'),
        }
        records.append(record)

    if break_it:
        for idx in range(min(50, len(records))):
            records[idx]["amount"] = None
        # Drop customer values by not writing the column

    try:
        with OUTPUT_FILE.open("w", newline='', encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            for record in records:
                if break_it:
                    row = {k: record[k] for k in headers}
                else:
                    row = record
                writer.writerow(row)
        print(f"Generated {rows} rows to {OUTPUT_FILE}")
    except OSError as exc:
        print(f"Failed to write data file: {exc}")


if __name__ == "__main__":
    generate_data(break_it=True)
