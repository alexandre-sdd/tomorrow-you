"""
Cross-layer consistency test.

Validates that:
1. Reference session.json contains all required fields
2. Backend Pydantic models can round-trip every stored object
3. Serialized keys match camelCase expected by frontend types.ts
4. Memory nodes, branches, exploration paths, and full tree are mutually consistent
5. Conversational agent prerequisites are met (selfCard has personality fields)
"""

import json
import sys
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.models.schemas import SelfCard, UserProfile, VisualStyle

SESSION_PATH = Path("storage/sessions/user_nyc_singapore_001/session.json")

def main() -> None:
    d = json.loads(SESSION_PATH.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------
    # 1. Top-level keys
    # ---------------------------------------------------------------
    required_top = [
        "id", "status", "transcript", "userProfile", "currentSelf",
        "futureSelfOptions", "selectedFutureSelf", "memoryHead",
        "memoryBranches", "memoryNodes", "createdAt", "updatedAt",
        "futureSelvesFull", "explorationPaths",
    ]
    for k in required_top:
        assert k in d, f"Missing top-level key: {k}"
    print(f"[OK] All {len(required_top)} top-level keys present")

    # ---------------------------------------------------------------
    # 2. Pydantic round-trip: currentSelf
    # ---------------------------------------------------------------
    cs = SelfCard.model_validate(d["currentSelf"])
    assert cs.depth_level == 0, "currentSelf depth should be 0"
    assert cs.parent_self_id is None
    print(f"[OK] currentSelf round-trips: {cs.name}, depth={cs.depth_level}")

    # ---------------------------------------------------------------
    # 3. Pydantic round-trip: futureSelfOptions
    # ---------------------------------------------------------------
    for opt in d["futureSelfOptions"]:
        card = SelfCard.model_validate(opt)
        assert card.depth_level >= 1
        assert "parentSelfId" in opt, "futureSelfOptions entry missing parentSelfId"
        assert "depthLevel" in opt, "futureSelfOptions entry missing depthLevel"
        assert "childrenIds" in opt, "futureSelfOptions entry missing childrenIds"
    print(f"[OK] {len(d['futureSelfOptions'])} futureSelfOptions round-trip")

    # ---------------------------------------------------------------
    # 4. Pydantic round-trip: futureSelvesFull
    # ---------------------------------------------------------------
    for sid, sdata in d["futureSelvesFull"].items():
        card = SelfCard.model_validate(sdata)
        assert card.id == sid, f"ID mismatch in futureSelvesFull: {card.id} vs {sid}"
    print(f"[OK] {len(d['futureSelvesFull'])} futureSelvesFull entries round-trip")

    # ---------------------------------------------------------------
    # 5. futureSelfOptions ⊆ futureSelvesFull
    # ---------------------------------------------------------------
    for opt in d["futureSelfOptions"]:
        sid = opt["id"]
        assert sid in d["futureSelvesFull"], f"{sid} in options but not in full tree"
        assert opt["name"] == d["futureSelvesFull"][sid]["name"]
    print("[OK] futureSelfOptions is subset of futureSelvesFull")

    # ---------------------------------------------------------------
    # 6. explorationPaths → valid IDs
    # ---------------------------------------------------------------
    for parent_key, children in d["explorationPaths"].items():
        for child_id in children:
            assert child_id in d["futureSelvesFull"], \
                f"{child_id} in explorationPaths but not in futureSelvesFull"
    print(f"[OK] explorationPaths references are valid ({len(d['explorationPaths'])} paths)")

    # ---------------------------------------------------------------
    # 7. memoryNodes selfCards have tree fields
    # ---------------------------------------------------------------
    for node in d["memoryNodes"]:
        sc = node.get("selfCard")
        if sc:
            card = SelfCard.model_validate(sc)
            assert "parentSelfId" in sc
            assert "depthLevel" in sc
            assert "childrenIds" in sc
    print(f"[OK] {len(d['memoryNodes'])} memoryNodes selfCards have tree fields")

    # ---------------------------------------------------------------
    # 8. memoryBranches ↔ memoryNodes cross-ref
    # ---------------------------------------------------------------
    node_ids = {n["id"] for n in d["memoryNodes"]}
    for branch in d["memoryBranches"]:
        assert branch["headNodeId"] in node_ids, \
            f"Branch '{branch['name']}' headNodeId '{branch['headNodeId']}' not in memoryNodes"
    print(f"[OK] {len(d['memoryBranches'])} memoryBranches → memoryNodes cross-ref valid")

    # ---------------------------------------------------------------
    # 9. Serialization key check (camelCase for frontend)
    # ---------------------------------------------------------------
    frontend_self_keys = {
        "id", "type", "name", "optimizationGoal", "toneOfVoice",
        "worldview", "coreBelief", "tradeOff", "avatarPrompt",
        "avatarUrl", "visualStyle", "voiceId",
        "parentSelfId", "depthLevel", "childrenIds",
    }
    for sid, sdata in d["futureSelvesFull"].items():
        missing = frontend_self_keys - set(sdata.keys())
        assert not missing, f"SelfCard {sid} missing frontend keys: {missing}"
    print("[OK] All futureSelvesFull entries have correct camelCase keys for frontend")

    # ---------------------------------------------------------------
    # 10. Conversation engine prerequisites
    # ---------------------------------------------------------------
    conversation_fields = [
        "name", "toneOfVoice", "worldview", "coreBelief",
        "optimizationGoal", "tradeOff", "voiceId",
    ]
    for sid, sdata in d["futureSelvesFull"].items():
        for field in conversation_fields:
            val = sdata.get(field)
            assert val and isinstance(val, str) and len(val) > 0, \
                f"SelfCard {sid} has empty/missing '{field}' — conversation agent needs this"
    print("[OK] All future selves have non-empty personality fields for conversation agent")

    # ---------------------------------------------------------------
    # 11. UserProfile round-trip
    # ---------------------------------------------------------------
    profile = UserProfile.model_validate(d["userProfile"])
    assert len(profile.core_values) > 0
    assert len(profile.fears) > 0
    assert profile.current_dilemma
    print(f"[OK] UserProfile round-trips: {len(profile.core_values)} values, {len(profile.fears)} fears")

    print("\n=== ALL CONSISTENCY CHECKS PASSED ===")


if __name__ == "__main__":
    main()
