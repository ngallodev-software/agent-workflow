def normalize_records(records):
    values = {}
    for record in records:
        key = record["id"].strip().casefold()
        values.setdefault(key, {**record, "id": key})
    return [values[key] for key in sorted(values)]
