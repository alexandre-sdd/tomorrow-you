from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from backend.config.settings import Settings, get_settings
from backend.engines.future_self_generator import FutureSelfGenerator
from backend.models.schemas import (
    GenerateFutureSelvesRequest,
    GenerateFutureSelvesResponse,
    SelfCard,
    UserProfile,
)

router = APIRouter(prefix="/future-self", tags=["future-self"])

# Module-level engine instance (stateless — safe to share across requests)
_generator = FutureSelfGenerator()


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _session_dir(session_id: str, storage_path: str) -> Path:
    return Path(storage_path) / session_id


def _load_session(session_id: str, storage_path: str) -> dict:
    session_file = _session_dir(session_id, storage_path) / "session.json"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return json.loads(session_file.read_text(encoding="utf-8"))


def _save_session(session_id: str, storage_path: str, data: dict) -> None:
    session_file = _session_dir(session_id, storage_path) / "session.json"
    session_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _append_transcript_entry(
    session_id: str, storage_path: str, entry: dict
) -> None:
    transcript_file = _session_dir(session_id, storage_path) / "transcript.json"
    transcript = (
        json.loads(transcript_file.read_text(encoding="utf-8"))
        if transcript_file.exists()
        else []
    )
    transcript.append(entry)
    transcript_file.write_text(json.dumps(transcript, indent=2), encoding="utf-8")


def _find_root_node_id(session_id: str, storage_path: str) -> str:
    """Find the root memory node ID (node with parentId=null)"""
    nodes_dir = _session_dir(session_id, storage_path) / "memory" / "nodes"
    for node_file in nodes_dir.glob("*.json"):
        node = json.loads(node_file.read_text(encoding="utf-8"))
        if node.get("parentId") is None:
            return node["id"]
    raise ValueError("Root node not found")


def _find_node_id_for_self(session_id: str, storage_path: str, self_id: str) -> str:
    """Find the memory node ID for a given self_id"""
    nodes_dir = _session_dir(session_id, storage_path) / "memory" / "nodes"
    for node_file in nodes_dir.glob("*.json"):
        node = json.loads(node_file.read_text(encoding="utf-8"))
        self_card = node.get("selfCard")
        if self_card and self_card.get("id") == self_id:
            return node["id"]
    raise ValueError(f"Node for self '{self_id}' not found")


def _create_memory_branches(
    session_id: str,
    storage_path: str,
    future_selves: list[SelfCard],
    parent_node_id: str,
    parent_branch_name: str,
    now: float,
    session_data: dict,
) -> None:
    """
    For each generated future self:
    - Write an initial MemoryNode to memory/nodes/{node_id}.json
    - Append a MemoryBranch entry to memory/branches.json

    Supports multi-level branching by linking to parent node and branch.
    Idempotent — skips branches that already exist by name.
    Also updates session_data['memoryBranches'] in place so the caller
    can persist it back to session.json.
    """
    nodes_dir = _session_dir(session_id, storage_path) / "memory" / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    branches_file = _session_dir(session_id, storage_path) / "memory" / "branches.json"
    branches: list[dict] = (
        json.loads(branches_file.read_text(encoding="utf-8"))
        if branches_file.exists()
        else []
    )

    existing_branch_names = {b["name"] for b in branches}

    for self_card in future_selves:
        branch_name = self_card.name.lower().replace(" ", "-")
        if branch_name in existing_branch_names:
            continue  # idempotent

        node_id = f"node_branch_{uuid.uuid4().hex[:8]}"

        node_data = {
            "id": node_id,
            "parentId": parent_node_id,
            "branchLabel": branch_name,
            "facts": [
                {
                    "id": f"fact_{uuid.uuid4().hex[:8]}",
                    "fact": f"Optimizes for: {self_card.optimization_goal}",
                    "source": "interview",
                    "extractedAt": now,
                }
            ],
            "notes": [f"Branch node for: {self_card.name} (parent: {parent_branch_name})"],
            "selfCard": self_card.model_dump(by_alias=True),
            "createdAt": now,
        }
        (nodes_dir / f"{node_id}.json").write_text(
            json.dumps(node_data, indent=2), encoding="utf-8"
        )

        branches.append(
            {
                "name": branch_name,
                "headNodeId": node_id,
                "parentBranchName": parent_branch_name,
            }
        )
        existing_branch_names.add(branch_name)

    branches_file.write_text(json.dumps(branches, indent=2), encoding="utf-8")
    session_data["memoryBranches"] = branches

    # Keep session_data["memoryNodes"] in sync (inline array mirrors files)
    if "memoryNodes" not in session_data:
        session_data["memoryNodes"] = []
    existing_node_ids = {n["id"] for n in session_data["memoryNodes"]}
    for node_file in nodes_dir.glob("*.json"):
        node = json.loads(node_file.read_text(encoding="utf-8"))
        if node["id"] not in existing_node_ids:
            session_data["memoryNodes"].append(node)
            existing_node_ids.add(node["id"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=GenerateFutureSelvesResponse)
async def generate_future_selves(
    request: GenerateFutureSelvesRequest,
    settings: Settings = Depends(get_settings),
) -> GenerateFutureSelvesResponse:
    """
    Generate future self personas. Supports multi-level branching.
    
    - If parent_self_id is None: Generate root-level futures from current dilemma
    - If parent_self_id is set: Generate secondary futures exploring that path's evolution
    
    Tree structure preserved in session — nothing is ever lost.
    All generated selves stored in futureSelvesFull, exploration paths tracked.
    """
    # 1. Load session from disk
    session_data = _load_session(request.session_id, settings.storage_path)
    
    # 2. Initialize tree structures if not present
    if "futureSelvesFull" not in session_data:
        session_data["futureSelvesFull"] = {}
    if "explorationPaths" not in session_data:
        session_data["explorationPaths"] = {}

    # 3. Validate preconditions
    raw_profile = session_data.get("userProfile")
    if not raw_profile:
        raise HTTPException(
            status_code=400,
            detail="Session is missing 'userProfile' — run profile build first",
        )

    user_profile = UserProfile.model_validate(raw_profile)

    # 4. Branch: Root generation vs Secondary generation
    if request.parent_self_id is None:
        # ROOT LEVEL GENERATION
        raw_current_self = session_data.get("currentSelf")
        if not raw_current_self:
            raise HTTPException(
                status_code=400,
                detail="Session is missing 'currentSelf' — run profile build first",
            )
        
        current_self = SelfCard.model_validate(raw_current_self)
        
        try:
            future_selves = await _generator.generate(
                user_profile=user_profile,
                current_self=current_self,
                count=request.count,
            )
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        
        parent_key = "root"
        parent_node_id = _find_root_node_id(request.session_id, settings.storage_path)
        parent_branch_name = "root"
        level_desc = "root level"

        # Set tree metadata on root-level selves
        for card in future_selves:
            card.parent_self_id = None
            card.depth_level = 1
            card.children_ids = []
        
    else:
        # SECONDARY LEVEL GENERATION
        parent_self_data = session_data["futureSelvesFull"].get(request.parent_self_id)
        if not parent_self_data:
            raise HTTPException(
                status_code=404,
                detail=f"Parent self '{request.parent_self_id}' not found in session"
            )
        
        parent_self = SelfCard.model_validate(parent_self_data)
        
        try:
            future_selves = await _generator.generate_secondary(
                parent_self=parent_self,
                user_profile=user_profile,
                count=request.count,
            )
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        
        parent_key = request.parent_self_id
        parent_node_id = _find_node_id_for_self(
            request.session_id, settings.storage_path, request.parent_self_id
        )
        parent_branch_name = parent_self.name.lower().replace(" ", "-")
        level_desc = f"from '{parent_self.name}'"
        
        # Update parent's children_ids
        if parent_self.id in session_data["futureSelvesFull"]:
            existing_children = session_data["futureSelvesFull"][parent_self.id].get("childrenIds", [])
            session_data["futureSelvesFull"][parent_self.id]["childrenIds"] = [
                *existing_children,
                *[s.id for s in future_selves]
            ]

    # 5. Update session tree structures
    now = time.time()
    
    # Add to full tree (preserves all selves)
    for self_card in future_selves:
        session_data["futureSelvesFull"][self_card.id] = self_card.model_dump(by_alias=True)
    
    # Track exploration path
    if parent_key not in session_data["explorationPaths"]:
        session_data["explorationPaths"][parent_key] = []
    session_data["explorationPaths"][parent_key].extend([s.id for s in future_selves])
    
    # Update futureSelfOptions (backward compat - only root level)
    if request.parent_self_id is None:
        session_data["futureSelfOptions"] = [
            s.model_dump(by_alias=True) for s in future_selves
        ]
        session_data["status"] = "selection"
    
    session_data["updatedAt"] = now

    # 6. Create memory branch nodes
    _create_memory_branches(
        session_id=request.session_id,
        storage_path=settings.storage_path,
        future_selves=future_selves,
        parent_node_id=parent_node_id,
        parent_branch_name=parent_branch_name,
        now=now,
        session_data=session_data,
    )

    # 7. Persist updated session
    _save_session(request.session_id, settings.storage_path, session_data)

    # 8. Append system transcript entry
    self_names = ", ".join(s.name for s in future_selves)
    _append_transcript_entry(
        request.session_id,
        settings.storage_path,
        {
            "id": f"te_{uuid.uuid4().hex[:8]}",
            "turn": len(session_data.get("transcript", [])) + 1,
            "phase": "selection",
            "role": "system",
            "selfName": None,
            "content": f"Generated {len(future_selves)} futures ({level_desc}): {self_names}",
            "timestamp": now,
        },
    )

    return GenerateFutureSelvesResponse(
        session_id=request.session_id,
        future_self_options=future_selves,
        generated_at=now,
    )


# ---------------------------------------------------------------------------
# Tree Navigation Endpoints
# ---------------------------------------------------------------------------

@router.get("/{session_id}/tree")
async def get_future_self_tree(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Get the full exploration tree for navigation.
    
    Returns all generated future selves and their relationships,
    allowing the client to render the tree and navigate between branches.
    """
    session_data = _load_session(session_id, settings.storage_path)
    
    return {
        "sessionId": session_id,
        "allSelves": session_data.get("futureSelvesFull", {}),
        "explorationPaths": session_data.get("explorationPaths", {}),
        "rootOptions": session_data.get("futureSelfOptions", []),
    }


@router.get("/{session_id}/self/{self_id}/children")
async def get_self_children(
    session_id: str,
    self_id: str,
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    """
    Get children of a specific future self.
    
    Returns the list of future selves that were generated as secondary
    branches from the specified parent self. Returns empty array if no
    children have been generated yet.
    """
    session_data = _load_session(session_id, settings.storage_path)
    
    self_data = session_data.get("futureSelvesFull", {}).get(self_id)
    if not self_data:
        raise HTTPException(
            status_code=404,
            detail=f"Self '{self_id}' not found in session"
        )
    
    children_ids = self_data.get("childrenIds", [])
    children = [
        session_data["futureSelvesFull"][child_id]
        for child_id in children_ids
        if child_id in session_data["futureSelvesFull"]
    ]
    
    return children
