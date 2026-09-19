"""Host-owned persistence for plugin-independent comparative decision evidence."""
from __future__ import annotations
import json, sqlite3
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from .comparative_eval import require_shared_library

class EvidenceStore:
    def __init__(self,path:str|Path)->None:
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(self.path))
        self.db.execute("CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS outcomes (id TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(id, kind))")
        self.db.commit()
    def observation(self,observation_id:str)->dict[str,Any]|None:
        row=self.db.execute("SELECT payload FROM observations WHERE id=?",(observation_id,)).fetchone()
        return json.loads(row[0]) if row else None
    def put_observation(self,record:Mapping[str,Any])->dict[str,Any]:
        lib=require_shared_library(); lib.validate_observation(record)
        payload=json.dumps(record,sort_keys=True,separators=(",",":"))
        try:self.db.execute("INSERT INTO observations VALUES (?,?)",(record["observation_id"],payload))
        except sqlite3.IntegrityError:
            row=self.db.execute("SELECT payload FROM observations WHERE id=?",(record["observation_id"],)).fetchone()
            if row is None or row[0]!=payload: raise ValueError("observation ID already contains different evidence")
        self.db.commit(); return dict(record)
    def put_outcome(self,record:Mapping[str,Any])->dict[str,Any]:
        payload=json.dumps(record,sort_keys=True,separators=(",",":"))
        try:self.db.execute("INSERT INTO outcomes VALUES (?,?,?)",(record["observation_id"],record["outcome_kind"],payload))
        except sqlite3.IntegrityError:
            row=self.db.execute("SELECT payload FROM outcomes WHERE id=? AND kind=?",(record["observation_id"],record["outcome_kind"])).fetchone()
            if row is None or json.loads(row[0]).get("outcome")!=dict(record.get("outcome",{})): raise ValueError("outcome key already contains different evidence")
        self.db.commit(); return dict(record)
    def observations(self)->list[dict[str,Any]]:
        return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM observations ORDER BY id")]
    def outcomes(self)->list[dict[str,Any]]:
        return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM outcomes ORDER BY id,kind")]
    def reports(self)->list[dict[str,Any]]:
        lib=require_shared_library(); groups={}
        for obs in self.observations():
            key=json.dumps((obs["feature_id"],obs["mode"],obs["identity"]),sort_keys=True)
            groups.setdefault(key,[]).append(obs)
        outcomes=self.outcomes(); result=[]
        for items in groups.values():
            ids={x["observation_id"] for x in items}
            result.append(lib.comparison_report(items,[x for x in outcomes if x["observation_id"] in ids]))
        return result
    def close(self)->None:self.db.close()

def make_precomputed_observation(*,feature_id:str,identity:Mapping[str,Any],source_input:Mapping[str,Any],projected_input:Mapping[str,Any],control_result:Mapping[str,Any],candidate_result:Mapping[str,Any],control_duration_seconds:float|None,candidate_duration_seconds:float|None,provider_elapsed_seconds:float|None=None,case_id:str|None=None,observation_id:str|None=None)->dict[str,Any]:
    """Create a shared observation without re-executing either decision arm."""
    lib=require_shared_library()
    record=lib.make_observation(feature_id=feature_id,mode="shadow-normal-usage",identity=dict(identity),source_input=dict(source_input),projected_input=dict(projected_input),case_id=case_id,data_class="production-metadata",observation_id=observation_id or str(uuid4()),control=lambda:dict(control_result),candidate=lambda:dict(candidate_result),candidate_applied=False,authoritative_arm="control")
    if control_duration_seconds is not None: record["control"]["duration_seconds"]=float(control_duration_seconds)
    if candidate_duration_seconds is not None: record["candidate"]["duration_seconds"]=float(candidate_duration_seconds)
    if provider_elapsed_seconds is not None: record["candidate"]["provider_elapsed_seconds"]=float(provider_elapsed_seconds)
    lib.validate_observation(record); return record

def join_agent_run_outcome(store:EvidenceStore,observation_id:str,outcome:Mapping[str,Any])->dict[str,Any]:
    for current in store.outcomes():
        if current["observation_id"]==observation_id and current["outcome_kind"]=="agent-run-outcome":
            if current["outcome"]!=dict(outcome): raise ValueError("agent-run outcome conflicts with immutable prior evidence")
            return current
    lib=require_shared_library(); record=lib.make_outcome(observation_id,"agent-run-outcome",dict(outcome)); return store.put_outcome(record)
