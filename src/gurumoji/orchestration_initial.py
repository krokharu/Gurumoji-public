"""Versioned, JSON-only checkpoints for deterministic initial analysis stages.

This store never executes a stage or starts a worker. Completed outputs are
immutable, linked to frozen inputs and all predecessor hashes. Recovery requires
an explicit run resume; an interrupted deterministic stage may be recalculated.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .analysis_core import AnalysisContractError, canonical, fingerprint


@dataclass(frozen=True)
class InitialStage:
    stage_id: str
    label: str
    version: str = "1"


def encoded(value: Any) -> str:
    return canonical(value).decode("utf-8")


def initialize_initial_checkpoints(db):
    db.execute("""CREATE TABLE IF NOT EXISTS orchestration_initial_builds (
        initial_id TEXT PRIMARY KEY, builder_version TEXT NOT NULL,
        spec_json TEXT NOT NULL, frozen_json TEXT NOT NULL, frozen_hash TEXT NOT NULL,
        source_hash TEXT NOT NULL, owner_run_id TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS orchestration_initial_stages (
        initial_id TEXT NOT NULL, stage_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
        state_json TEXT NOT NULL, output_json TEXT,
        PRIMARY KEY(initial_id,stage_id))""")


def _spec(builder):
    return [{"stage_id": stage.stage_id, "label": stage.label, "version": stage.version}
            for stage in builder.stages]


def create_initial_checkpoints(db, initial_id, builder, frozen, source_hash, owner_run_id):
    spec = _spec(builder)
    if not spec or len({s["stage_id"] for s in spec}) != len(spec):
        raise ValueError("Initial stages must be nonempty and unique")
    db.execute("INSERT INTO orchestration_initial_builds VALUES (?,?,?,?,?,?,?)",
               (initial_id, builder.version, encoded(spec), encoded(frozen), fingerprint(frozen), source_hash, owner_run_id))
    for ordinal, stage in enumerate(spec):
        state = {**stage, "status": "pending", "attempt_count": 0, "input_hash": None,
                 "output_hash": None, "started_at": None, "completed_at": None, "error": ""}
        db.execute("INSERT INTO orchestration_initial_stages VALUES (?,?,?,?,NULL)",
                   (initial_id, stage["stage_id"], ordinal, encoded(state)))


def stage_input_hash(build, stage, predecessors):
    return fingerprint({"source_hash": build["source_hash"], "frozen_hash": build["frozen_hash"],
                        "builder_version": build["builder_version"], "stage_id": stage["stage_id"],
                        "stage_version": stage["version"], "predecessors": predecessors})


def read_initial_checkpoints(db, initial_id, builder):
    """Validate the complete chain before returning any reusable output."""
    build = db.execute("SELECT * FROM orchestration_initial_builds WHERE initial_id=?", (initial_id,)).fetchone()
    if build is None:
        raise AnalysisContractError("初期分析の段階記録がありません。", code="initial_checkpoint_missing")
    if build["builder_version"] != builder.version or json.loads(build["spec_json"]) != _spec(builder):
        raise AnalysisContractError("初期分析のアルゴリズム版が変わりました。元の版で復旧してください。", code="initial_version_conflict")
    frozen = json.loads(build["frozen_json"])
    if fingerprint(frozen) != build["frozen_hash"]:
        raise AnalysisContractError("初期入力の保存hashが一致しません。", code="initial_hash_mismatch")
    rows = db.execute("SELECT * FROM orchestration_initial_stages WHERE initial_id=? ORDER BY ordinal", (initial_id,)).fetchall()
    if len(rows) != len(builder.stages):
        raise AnalysisContractError("初期分析の段階記録が欠落しています。", code="initial_checkpoint_missing")
    outputs, hashes, states = {}, {}, []
    unfinished = False
    for ordinal, row in enumerate(rows):
        state = json.loads(row["state_json"])
        expected = _spec(builder)[ordinal]
        if (row["ordinal"] != ordinal or row["stage_id"] != expected["stage_id"]
                or any(state.get(key) != value for key, value in expected.items())):
            raise AnalysisContractError("初期分析の段階版が一致しません。", code="initial_version_conflict")
        if state.get("status") not in {"pending", "running", "completed", "failed"}:
            raise AnalysisContractError("初期分析の段階状態が不正です。", code="initial_checkpoint_invalid")
        if state["status"] == "completed":
            if unfinished or row["output_json"] is None:
                raise AnalysisContractError("初期分析の段階順序が壊れています。", code="initial_checkpoint_missing")
            output = json.loads(row["output_json"])
            if (fingerprint(output) != state["output_hash"]
                    or state["input_hash"] != stage_input_hash(build, state, hashes)):
                raise AnalysisContractError("初期分析の段階hashが一致しません。", code="initial_hash_mismatch")
            outputs[state["stage_id"]] = output
            hashes[state["stage_id"]] = state["output_hash"]
        else:
            unfinished = True
            if row["output_json"] is not None or state["output_hash"] is not None:
                raise AnalysisContractError("未完了段階に出力が混在しています。", code="initial_hash_mismatch")
        states.append(state)
    return build, frozen, states, outputs, hashes


def write_stage(db, initial_id, state, output=None):
    db.execute("UPDATE orchestration_initial_stages SET state_json=?,output_json=? WHERE initial_id=? AND stage_id=?",
               (encoded(state), encoded(output) if state["status"] == "completed" else None, initial_id, state["stage_id"]))


def initial_progress(db, initial_id):
    initial = db.execute("SELECT * FROM orchestration_initials WHERE initial_id=?", (initial_id,)).fetchone()
    build = db.execute("SELECT builder_version,frozen_hash,source_hash FROM orchestration_initial_builds WHERE initial_id=?", (initial_id,)).fetchone()
    stages = [json.loads(row[0]) for row in db.execute(
        "SELECT state_json FROM orchestration_initial_stages WHERE initial_id=? ORDER BY ordinal", (initial_id,))]
    public = [{**state, "id": state["stage_id"], "artifact_hash": state["output_hash"], "attempts": state["attempt_count"]}
              for state in stages]
    return {"initial_id": initial_id, "status": initial["status"] if initial else "missing",
            "builder_version": build[0] if build else "legacy",
            "frozen_input_hash": build[1] if build else None, "source_hash": build[2] if build else None,
            "completed_stages": sum(s["status"] == "completed" for s in stages), "total_stages": len(stages),
            "current_stage": next((s["stage_id"] for s in stages if s["status"] != "completed"), None),
            "error": initial["error"] if initial else "initial_missing", "stages": public}


def recover_initial_checkpoints(db):
    """Startup marker only. Deterministic work is never executed here."""
    for row in db.execute("SELECT initial_id,state_json FROM orchestration_initial_stages").fetchall():
        state = json.loads(row[1])
        if state["status"] == "running":
            state.update(status="failed", error="initial_stage_interrupted")
            write_stage(db, row[0], state)
            db.execute("UPDATE orchestration_initials SET status='failed',error='initial_stage_interrupted' WHERE initial_id=? AND status!='ready'", (row[0],))
