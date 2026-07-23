def normalize_records(records):
    for record in records:
        record["id"] = record["id"].strip().casefold()
    return sorted(records, key=lambda item: item["id"])
