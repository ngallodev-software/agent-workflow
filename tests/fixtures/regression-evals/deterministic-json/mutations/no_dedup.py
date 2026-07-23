def normalize_records(records):
    return [{**record, "id": record["id"].strip().casefold()} for record in records]
