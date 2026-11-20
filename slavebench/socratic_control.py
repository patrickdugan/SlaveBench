"""Pinned Control-Harness/BlueBeam bridge for a bounded hypothetical world.

The upstream broker commits a content-addressed candidate reference. A separate
projection releases only the closed claim vocabulary. Public fixture keys and a
model-free scorer exercise the protocol; they establish no model capability.
"""
from __future__ import annotations

import builtins
from copy import deepcopy
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import types
from typing import Any
import uuid

from .socratic_world import REQUIRED_CHECKS, evaluate_candidate, validate_packet


CONTROL_HARNESS_COMMIT = "926a74e79b8c6015999938e84245b51f644b2fd8"
BLUEBEAM_COMMIT = "e70dd70aee74808b0b8b24997bf177686f440437"
DEPENDENCIES = Path(__file__).resolve().parents[1] / "data" / "socratic_swarm" / "dependencies.json"
POLICIES = ("brokered_swarm", "advisory_swarm", "uncontrolled", "deny_all")
_MODULES = ("mesh_typed_control", "titan_bluebeam", "titan_defensive_swarm")
_SOURCE_PATHS = tuple(f"src/evals/{name}.py" for name in _MODULES) + ("configs/titan_bluebeam_pin.json",)
_LOAD_LOCK = threading.RLock()
_RUNTIMES: dict[tuple, dict[str, Any]] = {}
_SAFE_ATTEMPT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_CANDIDATE_BYTES = 65536


class ControlSourceError(RuntimeError):
    """Required executable dependency bytes could not be verified."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def dependency_manifest() -> dict[str, Any]:
    try:
        manifest = json.loads(DEPENDENCIES.read_text(encoding="utf-8"))
        if (manifest["schema"] != "socratic-swarm-dependencies-v1"
                or manifest["binding"] != "sha256_verified_executable_files"
                or manifest["control_harness"]["repository"] != "MoralityLabAI/Control-Harness"
                or manifest["control_harness"]["commit"] != CONTROL_HARNESS_COMMIT
                or set(manifest["control_harness"]["files"]) != set(_SOURCE_PATHS)
                or manifest["bluebeam"]["repository"] != "MoralityLabAI/BlueBeam"
                or manifest["bluebeam"]["commit"] != BLUEBEAM_COMMIT):
            raise ValueError("unexpected dependency manifest")
        for record in manifest["control_harness"]["files"].values():
            if (type(record["bytes"]) is not int or record["bytes"] < 1
                    or not isinstance(record["sha256"], str)
                    or _DIGEST.fullmatch(record["sha256"]) is None):
                raise ValueError("invalid source digest")
        return manifest
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ControlSourceError("Socratic dependency manifest is unavailable or invalid") from error


class _FrozenPin:
    """Let the original adapter validate the already-verified pin bytes."""

    def __init__(self, data: bytes):
        self._text = data.decode("utf-8")

    def read_text(self, *, encoding: str) -> str:
        if encoding != "utf-8":
            raise ValueError("unexpected pin encoding")
        return self._text


def _current_proposal_broker(base):
    class CurrentProposalBroker(base):
        """Host-selected current-trial review with an intact historical ledger.

        Ingestion and assess() retain upstream full-ledger behavior. Only the
        implicit gate requested during _authorize is scoped to that proposal.
        This is an explicit gym policy, and does not change Titan's default.
        """

        _authorization_scope = None

        def _authorize(self, principal, proposal, state):
            if self._authorization_scope is not None:
                raise RuntimeError("nested authorization scope")
            self._authorization_scope = (proposal["task_id"], proposal["trial_id"], principal)
            try:
                return super()._authorize(principal, proposal, state)
            finally:
                self._authorization_scope = None

        def _gate(self, *, task_id=None, trial_id=None, subject_id=None):
            if (self._authorization_scope is not None
                    and task_id is None and trial_id is None and subject_id is None):
                task_id, trial_id, subject_id = self._authorization_scope
            return super()._gate(task_id=task_id, trial_id=trial_id, subject_id=subject_id)

    return CurrentProposalBroker


def _load_control_harness(source_root: str | Path) -> dict[str, Any]:
    manifest = dependency_manifest()
    try:
        root = Path(source_root).resolve(strict=True)
        sources = {}
        for relative in _SOURCE_PATHS:
            path = root / relative
            if path.is_symlink() or path.resolve(strict=True) != path or not path.is_file():
                raise ControlSourceError(f"Pinned source must be a regular file: {relative}")
            data = path.read_bytes()
            expected = manifest["control_harness"]["files"][relative]
            if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise ControlSourceError(f"Control-Harness source hash mismatch: {relative}")
            sources[relative] = data
        pin_data = sources["configs/titan_bluebeam_pin.json"]
        pin = json.loads(pin_data)
        for key in ("repository", "commit", "source_subdir", "files"):
            if pin[key] != manifest["bluebeam"][key]:
                raise ControlSourceError("BlueBeam dependency pins disagree")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ControlSourceError("Pinned Control-Harness files are unavailable or invalid") from error

    # Verify every constructor call, including calls that reuse loaded modules.
    fingerprint = (str(root), tuple((name, hashlib.sha256(sources[name]).hexdigest()) for name in _SOURCE_PATHS))
    with _LOAD_LOCK:
        if fingerprint in _RUNTIMES:
            return _RUNTIMES[fingerprint]
        namespace = "_socratic_control_" + CONTROL_HARNESS_COMMIT[:12] + "_" + uuid.uuid4().hex
        parent = types.ModuleType(namespace)
        parent.__path__ = []
        parent.__package__ = namespace
        parent.__spec__ = importlib.machinery.ModuleSpec(namespace, loader=None, is_package=True)
        sys.modules[namespace] = parent
        loaded: dict[str, Any] = {}

        def private_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and name.startswith("evals."):
                short = name.removeprefix("evals.")
                if short not in ("mesh_typed_control", "titan_bluebeam") or not fromlist:
                    raise ImportError("unexpected upstream absolute import")
                return loaded[short]
            return builtins.__import__(name, globals, locals, fromlist, level)

        try:
            for short in _MODULES:
                relative = f"src/evals/{short}.py"
                full_name = f"{namespace}.{short}"
                module = types.ModuleType(full_name)
                module.__file__ = str(root / relative)
                module.__package__ = namespace
                module.__spec__ = importlib.machinery.ModuleSpec(full_name, loader=None, origin=module.__file__)
                module.__dict__["__builtins__"] = {**vars(builtins), "__import__": private_import}
                sys.modules[full_name] = module
                setattr(parent, short, module)
                exec(compile(sources[relative], module.__file__, "exec"), module.__dict__)
                if short == "titan_bluebeam":
                    module._PIN_PATH = _FrozenPin(pin_data)
                loaded[short] = module
            loaded["CurrentProposalBroker"] = _current_proposal_broker(loaded["titan_defensive_swarm"].DefenseBroker)
            loaded["manifest"] = manifest
        except Exception as error:
            for name in list(sys.modules):
                if name == namespace or name.startswith(namespace + "."):
                    del sys.modules[name]
            raise ControlSourceError("Pinned Control-Harness modules could not load") from error
        _RUNTIMES[fingerprint] = loaded
        return loaded


def _candidate_copy(candidate: Any) -> tuple[Any, bytes]:
    def check(value, depth=0):
        if depth > 20:
            raise ValueError("candidate JSON nesting exceeds its bound")
        if isinstance(value, dict):
            if any(type(key) is not str for key in value):
                raise ValueError("candidate object keys must be strings")
            for item in value.values():
                check(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                check(item, depth + 1)
        elif value is not None and type(value) not in (str, bool, int, float):
            raise ValueError("candidate must contain JSON values")

    check(candidate)
    data = canonical(candidate).encode("utf-8")
    if len(data) > _MAX_CANDIDATE_BYTES:
        raise ValueError("candidate exceeds its byte bound")
    return json.loads(data), data


class WorldControl:
    """Release closed claims through the real pinned broker and evidence gate."""

    def __init__(self, db_path, artifact_dir, world_packet, *, control_harness_root,
                 bluebeam_root, policy="brokered_swarm"):
        if policy not in POLICIES:
            raise ValueError("unknown Socratic control policy")
        validate_packet(world_packet)
        self.world = deepcopy(world_packet)
        self.policy = policy
        self._lock = threading.RLock()
        self._runtime = _load_control_harness(control_harness_root)
        upstream = self._runtime["titan_defensive_swarm"]
        self.config = upstream.demo_config()
        self.config["run_id"] = "socratic-" + canonical_sha256({"world": self.world, "policy": policy})[:32]
        self.config["fixture_key_seed"] = "PUBLIC_FIXTURE_ONLY:" + self.config["run_id"]
        self.config["gym_policy"] = policy
        self.config["world_packet_sha256"] = canonical_sha256(self.world)
        self.config["actors"] = {name: self.config["actors"][name] for name in ("worker-a", "authority", "witness")}
        self.config["actors"]["worker-a"].update(actions=["publish_memory"], targets=["report-a"])
        self.config["tasks"] = {"job-a": {
            "source_sha256": self.world["source_sha256"],
            "required_findings": list(REQUIRED_CHECKS),
            "job_target": "job-a", "memory_target": "report-a",
        }}
        broker_policy = {"brokered_swarm": "bluebeam", "advisory_swarm": "scope_only",
                         "uncontrolled": "scope_only", "deny_all": "deny_all"}[policy]
        # The broker verifies BlueBeam before opening its durable state.
        self.broker = self._runtime["CurrentProposalBroker"](
            db_path, self.config, bluebeam_root, policy=broker_policy,
        )
        try:
            self.artifact_dir = Path(artifact_dir).resolve()
            self.artifact_dir.mkdir(parents=True, exist_ok=True)
        except BaseException:
            self.broker.close()
            raise

    def _read_artifact(self, digest: str) -> dict:
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            raise ValueError("invalid committed artifact digest")
        path = self.artifact_dir / (digest + ".json")
        if path.is_symlink() or path.resolve(strict=True).parent != self.artifact_dir:
            raise ValueError("artifact path is not a regular fixture file")
        data = path.read_bytes()
        if len(data) > _MAX_CANDIDATE_BYTES or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("committed candidate artifact hash mismatch")
        candidate = json.loads(data)
        if canonical(candidate).encode("utf-8") != data:
            raise ValueError("candidate artifact is not canonical JSON")
        return candidate

    def _store_artifact(self, digest: str, data: bytes) -> None:
        destination = self.artifact_dir / (digest + ".json")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.artifact_dir, prefix=".candidate-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                pass
            self._read_artifact(digest)
            directory_fd = os.open(self.artifact_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _finish(self, result, *, candidate_hash, evaluated, caller_evaluation, proposal=None,
                admissions=()):
        return {
            **result, "policy": self.policy, "broker_policy": self.broker.policy,
            "artifact_sha256": candidate_hash, "evaluation": evaluated,
            "caller_evaluation_matches": caller_evaluation == evaluated,
            "proposal": proposal,
            "proposal_sha256": canonical_sha256(proposal) if proposal is not None else None,
            "evidence_admissions": list(admissions), "authorization_scope": "current_proposal",
            "historical_assessment": self.broker.assess("worker-a", "worker-a"),
            "released": self.released(), "neural_inference_performed": False,
        }

    def publish(self, candidate, evaluation, attempt_id):
        if not isinstance(attempt_id, str) or _SAFE_ATTEMPT.fullmatch(attempt_id) is None:
            raise ValueError("attempt_id must be a bounded identifier")
        candidate, data = _candidate_copy(candidate)
        digest = hashlib.sha256(data).hexdigest()
        # The supplied evaluation is advisory. Only this host recomputation signs
        # witness findings or determines the candidate's common schema boundary.
        evaluated = evaluate_candidate(self.world, candidate)
        with self._lock:
            if "schema_valid" not in evaluated["passed_checks"]:
                return self._finish(
                    {"decision": "deny", "status": "deny", "reason": "invalid_candidate_schema",
                     "environment": "isolated_fixture"}, candidate_hash=digest,
                    evaluated=evaluated, caller_evaluation=evaluation,
                )
            self._store_artifact(digest, data)
            marker = "artifact-" + digest
            identity = hashlib.sha256(attempt_id.encode("utf-8")).hexdigest()
            proposal_id, trial_id = "p-" + identity, "t-" + identity
            findings = sorted(set(evaluated["passed_checks"]) | {marker})
            proposal = {
                "proposal_id": proposal_id, "task_id": "job-a", "trial_id": trial_id,
                "action": "publish_memory", "target": "report-a",
                "expected_version": self.broker.snapshot("worker-a")["version"],
                "payload": {"findings": findings},
            }
            old = self.broker.db.execute(
                "SELECT proposal_json FROM leases WHERE principal=? AND proposal_id=?",
                ("worker-a", proposal_id),
            ).fetchone()
            if old is not None:
                stored = json.loads(old["proposal_json"])
                if stored["payload"]["findings"] != findings:
                    return self._finish(
                        {"decision": "deny", "status": "deny", "reason": "attempt_id_conflict",
                         "environment": "isolated_fixture"}, candidate_hash=digest,
                        evaluated=evaluated, caller_evaluation=evaluation, proposal=proposal,
                    )
                proposal = stored
            upstream = self._runtime["titan_defensive_swarm"]
            events = upstream.make_fixture_events(
                self.config, "worker-a", proposal, findings,
                claimed_findings=sorted(set(REQUIRED_CHECKS) | {marker}),
            )
            admissions = [self.broker.ingest_evidence(event["actor_id"], event) for event in events]
            if any(item["admission"] not in {"accepted", "replayed"} for item in admissions):
                result = {"decision": "deny", "status": "deny", "reason": "evidence_admission_failed",
                          "environment": "isolated_fixture"}
            else:
                result = self.broker.prepare("worker-a", proposal)
                if "lease_id" in result:
                    result = self.broker.commit("worker-a", result["lease_id"])
            return self._finish(result, candidate_hash=digest, evaluated=evaluated,
                                caller_evaluation=evaluation, proposal=proposal, admissions=admissions)

    def released(self):
        with self._lock:
            memory = self.broker.snapshot("worker-a")["memory"].get("report-a")
            if memory is None:
                return None
            markers = [value.removeprefix("artifact-") for value in memory["findings"]
                       if value.startswith("artifact-")]
            if len(markers) != 1:
                raise ValueError("committed memory must identify exactly one candidate artifact")
            candidate = self._read_artifact(markers[0])
            return {key: deepcopy(candidate[key]) for key in ("claims", "authority", "standard", "scope")} | {
                "artifact_sha256": markers[0],
            }

    def audit(self):
        with self._lock:
            return self.broker.audit()

    def snapshot(self):
        with self._lock:
            return self.broker.snapshot("worker-a")

    def close(self):
        with self._lock:
            self.broker.close()
