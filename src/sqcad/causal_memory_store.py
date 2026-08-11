"""Minimal transactional store for evidence-backed causal-memory governance.

The prototype implements architectural invariants only.  It does not perform
LLM decomposition or causal-effect estimation.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional


VALID_STATUSES = {"active", "downweighted", "archived", "isolated"}
VALID_RULE_STATUSES = {"proposed", "active", "scoped", "archived", "isolated"}


@dataclass(frozen=True)
class RuleDecision:
    rule_id: str
    activated: bool
    reason: str


class CausalMemoryStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source_id TEXT NOT NULL,
                subject_scope TEXT NOT NULL,
                task_scope TEXT NOT NULL,
                available_at TEXT NOT NULL,
                status TEXT NOT NULL,
                restore_status TEXT
            );
            CREATE TABLE IF NOT EXISTS factor (
                factor_id TEXT PRIMARY KEY,
                evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
                factor_type TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                extractor_version TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS abstract_rule (
                rule_id TEXT PRIMARY KEY,
                statement TEXT NOT NULL,
                subject_scope TEXT NOT NULL,
                task_scope TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                stability REAL NOT NULL,
                evidence_coverage REAL NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rule_support (
                rule_id TEXT NOT NULL REFERENCES abstract_rule(rule_id),
                factor_id TEXT NOT NULL REFERENCES factor(factor_id),
                PRIMARY KEY (rule_id, factor_id)
            );
            CREATE TABLE IF NOT EXISTS governance_transition (
                transition_id TEXT PRIMARY KEY,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                old_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decision_log (
                decision_id TEXT PRIMARY KEY,
                episode_id TEXT NOT NULL,
                step INTEGER NOT NULL,
                history_json TEXT NOT NULL,
                candidates_json TEXT NOT NULL,
                behavior_action_json TEXT NOT NULL,
                propensity REAL NOT NULL,
                exposure_json TEXT NOT NULL,
                adoption_json TEXT NOT NULL,
                agent_action_json TEXT NOT NULL,
                outcome_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def add_evidence(
        self,
        content: str,
        source_id: str,
        subject_scope: str,
        task_scope: str,
        available_at: Optional[str] = None,
    ) -> str:
        evidence_id = self._id("ev")
        available_at = available_at or datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.execute(
                "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, 'active', NULL)",
                (evidence_id, content, source_id, subject_scope, task_scope, available_at),
            )
        return evidence_id

    def add_factor(
        self,
        evidence_id: str,
        factor_type: str,
        normalized_value: str,
        extractor_version: str,
        confidence: float,
    ) -> str:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        factor_id = self._id("fa")
        with self.conn:
            self.conn.execute(
                "INSERT INTO factor VALUES (?, ?, ?, ?, ?, ?, 'active')",
                (factor_id, evidence_id, factor_type, normalized_value, extractor_version, confidence),
            )
        return factor_id

    def propose_rule(
        self,
        statement: str,
        factor_ids: Iterable[str],
        subject_scope: str,
        task_scope: str,
        stability: float,
        evidence_coverage: float,
        rule_version: str = "v1",
    ) -> str:
        factors = list(dict.fromkeys(factor_ids))
        if not factors:
            raise ValueError("a rule requires at least one evidence-backed factor")
        if not 0.0 <= stability <= 1.0 or not 0.0 <= evidence_coverage <= 1.0:
            raise ValueError("stability and evidence coverage must be in [0, 1]")
        placeholders = ",".join("?" for _ in factors)
        rows = self.conn.execute(
            f"SELECT factor_id FROM factor WHERE factor_id IN ({placeholders})", factors
        ).fetchall()
        if len(rows) != len(factors):
            raise ValueError("all rule supports must reference existing factors")
        rule_id = self._id("ru")
        with self.conn:
            self.conn.execute(
                "INSERT INTO abstract_rule VALUES (?, ?, ?, ?, ?, ?, ?, 'proposed')",
                (rule_id, statement, subject_scope, task_scope, rule_version, stability, evidence_coverage),
            )
            self.conn.executemany(
                "INSERT INTO rule_support VALUES (?, ?)",
                [(rule_id, factor_id) for factor_id in factors],
            )
        return rule_id

    def try_activate_rule(
        self,
        rule_id: str,
        min_support: int = 2,
        min_stability: float = 0.8,
        min_coverage: float = 0.9,
    ) -> RuleDecision:
        rule = self.conn.execute(
            "SELECT * FROM abstract_rule WHERE rule_id = ?", (rule_id,)
        ).fetchone()
        if rule is None:
            raise KeyError(rule_id)
        supports = self.conn.execute(
            """
            SELECT f.factor_id, f.status AS factor_status, e.status AS evidence_status,
                   e.subject_scope, e.task_scope
            FROM rule_support rs
            JOIN factor f ON f.factor_id = rs.factor_id
            JOIN evidence e ON e.evidence_id = f.evidence_id
            WHERE rs.rule_id = ?
            """,
            (rule_id,),
        ).fetchall()
        reasons = []
        if len(supports) < min_support:
            reasons.append("insufficient_support")
        if rule["stability"] < min_stability:
            reasons.append("low_stability")
        if rule["evidence_coverage"] < min_coverage:
            reasons.append("low_evidence_coverage")
        if any(row["factor_status"] != "active" or row["evidence_status"] != "active" for row in supports):
            reasons.append("inactive_provenance")
        if any(
            row["subject_scope"] != rule["subject_scope"]
            or row["task_scope"] != rule["task_scope"]
            for row in supports
        ):
            reasons.append("scope_mismatch")
        if reasons:
            return RuleDecision(rule_id, False, ",".join(reasons))
        self._transition("rule", rule_id, "active", "activation_gates_passed")
        return RuleDecision(rule_id, True, "activation_gates_passed")

    def _transition(self, object_type: str, object_id: str, new_status: str, reason: str) -> None:
        table = "evidence" if object_type == "evidence" else "abstract_rule"
        valid = VALID_STATUSES if table == "evidence" else VALID_RULE_STATUSES
        if new_status not in valid:
            raise ValueError(f"invalid status: {new_status}")
        row = self.conn.execute(
            f"SELECT status FROM {table} WHERE {object_type}_id = ?", (object_id,)
        ).fetchone()
        if row is None:
            raise KeyError(object_id)
        old_status = row["status"]
        with self.conn:
            if table == "evidence" and new_status in {"archived", "isolated"}:
                self.conn.execute(
                    "UPDATE evidence SET restore_status = status, status = ? WHERE evidence_id = ?",
                    (new_status, object_id),
                )
            else:
                self.conn.execute(
                    f"UPDATE {table} SET status = ? WHERE {object_type}_id = ?",
                    (new_status, object_id),
                )
            self.conn.execute(
                "INSERT INTO governance_transition VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    self._id("tr"), object_type, object_id, old_status, new_status,
                    reason, datetime.now(timezone.utc).isoformat(),
                ),
            )

    def archive_evidence(self, evidence_id: str, reason: str) -> None:
        self._transition("evidence", evidence_id, "archived", reason)

    def downweight_evidence(self, evidence_id: str, reason: str) -> None:
        """Reversibly reduce default exposure without deleting provenance."""
        self._transition("evidence", evidence_id, "downweighted", reason)

    def isolate_evidence(self, evidence_id: str, reason: str) -> None:
        """Restrict default eligibility while retaining a restore path."""
        self._transition("evidence", evidence_id, "isolated", reason)

    def restore_evidence(self, evidence_id: str, reason: str) -> None:
        row = self.conn.execute(
            "SELECT status, restore_status FROM evidence WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
        if row is None:
            raise KeyError(evidence_id)
        if row["status"] not in {"downweighted", "archived", "isolated"}:
            raise ValueError("only downweighted, archived or isolated evidence can be restored")
        self._transition("evidence", evidence_id, row["restore_status"] or "active", reason)

    def eligible_rules(self, subject_scope: str, task_scope: str) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT * FROM abstract_rule
            WHERE status = 'active' AND subject_scope = ? AND task_scope = ?
            ORDER BY rule_id
            """,
            (subject_scope, task_scope),
        ).fetchall()

    def record_decision(
        self,
        episode_id: str,
        step: int,
        history: object,
        candidates: object,
        behavior_action: object,
        propensity: float,
        exposure: object,
        adoption: object,
        agent_action: object,
        outcome: object,
        decision_id: Optional[str] = None,
    ) -> str:
        """Atomically persist one causal decision tuple for replay/audit.

        Structured JSON payloads keep the storage hierarchy configurable while
        the propensity remains a first-class scalar for IPW/DR/OPE analyses.
        """
        if not episode_id:
            raise ValueError("episode_id must be non-empty")
        if step < 0:
            raise ValueError("step must be non-negative")
        if not 0.0 < propensity <= 1.0:
            raise ValueError("propensity must be in (0, 1]")
        decision_id = decision_id or self._id("dc")
        payload = (
            decision_id,
            episode_id,
            int(step),
            json.dumps(history, ensure_ascii=False, sort_keys=True),
            json.dumps(candidates, ensure_ascii=False, sort_keys=True),
            json.dumps(behavior_action, ensure_ascii=False, sort_keys=True),
            float(propensity),
            json.dumps(exposure, ensure_ascii=False, sort_keys=True),
            json.dumps(adoption, ensure_ascii=False, sort_keys=True),
            json.dumps(agent_action, ensure_ascii=False, sort_keys=True),
            json.dumps(outcome, ensure_ascii=False, sort_keys=True),
            datetime.now(timezone.utc).isoformat(),
        )
        with self.conn:
            self.conn.execute(
                "INSERT INTO decision_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                payload,
            )
        return decision_id

    def decisions(self, episode_id: Optional[str] = None) -> List[sqlite3.Row]:
        """Return decision logs in episode/step order for replay and auditing."""
        if episode_id is None:
            return self.conn.execute(
                "SELECT * FROM decision_log ORDER BY episode_id, step, decision_id"
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM decision_log WHERE episode_id = ? ORDER BY step, decision_id",
            (episode_id,),
        ).fetchall()

    def provenance(self, rule_id: str) -> List[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT r.rule_id, f.factor_id, f.factor_type, f.normalized_value,
                   e.evidence_id, e.source_id, e.content, e.status AS evidence_status
            FROM abstract_rule r
            JOIN rule_support rs ON rs.rule_id = r.rule_id
            JOIN factor f ON f.factor_id = rs.factor_id
            JOIN evidence e ON e.evidence_id = f.evidence_id
            WHERE r.rule_id = ? ORDER BY f.factor_id
            """,
            (rule_id,),
        ).fetchall()

    def audit_log(self) -> str:
        rows = [dict(row) for row in self.conn.execute("SELECT * FROM governance_transition ORDER BY created_at")]
        return json.dumps(rows, ensure_ascii=False, indent=2)
