# Storage — Session Persistence with Git-Like Memory Branching

## Purpose
Stores all session data with a **git-like branching memory system**. The transcript is a linear, append-only log of everything that happened. The memory is a tree of notes and sub-notes that branches at every decision point (future self selection, conversation fork). You can backtrack up the tree to explore a different branch without losing what was explored before.

## Two Separate Concerns

### 1. Transcript (Linear Log — never branches)
The transcript is a flat, chronological record of every exchange. It never forks. It captures:
- Every interview question and answer
- Every conversation turn with every future self
- Which self was selected, when, and what happened after

Think of this as `git log` — a linear history of all events in order. Even when the user backtracks to explore a different future self, the transcript records "user returned to selection" as a new entry. Nothing is deleted or overwritten.

```
transcript: [
  { turn: 1, phase: "interview", role: "interviewer", content: "..." },
  { turn: 2, phase: "interview", role: "user", content: "..." },
  ...
  { turn: 15, phase: "conversation", self: "The Architect", role: "future_self", content: "..." },
  { turn: 16, phase: "backtrack", from: "The Architect", to: "selection" },
  { turn: 17, phase: "conversation", self: "The Wanderer", role: "future_self", content: "..." },
]
```

### 2. Memory Tree (Branches at decision points)
The memory is a **tree of notes** that mirrors how git branches work. Each node in the tree holds extracted facts, insights, and context relevant to that point in the exploration.

```
                    [root: profile extracted]
                    ├── core values: freedom, creativity
                    ├── dilemma: stay at job vs. start company
                    ├── fear: wasting potential
                    │
                ┌───┴───────────────────┐
                │                       │
        [branch: The Architect]   [branch: The Wanderer]
        ├── optimizes: ambition    ├── optimizes: peace
        ├── note: user resonated   ├── note: user pushed back
        │   with "build legacy"    │   on "let go of control"
        ├── fact: user has a       ├── fact: user mentioned
        │   startup idea           │   traveling alone
        │                          │
        ├── [sub-branch: deeper    └── [sub-branch: pressed
        │    conversation]              on sacrifice]
        │   ├── user admitted          ├── user got emotional
        │   │   fear of failure        ├── mentioned childhood
        │   └── key moment:            └── key moment:
        │       "what if I'm not           "I never let myself
        │        good enough"               just exist"
        └──
```

## How Branching Works

### Commits (Nodes)
Each node in the memory tree is a **commit** — a snapshot of extracted knowledge at a point in time.
```
MemoryNode {
  id: string                    // unique node ID
  parentId: string | null       // parent node (null for root)
  branchLabel: string           // e.g. "root", "The Architect", "deeper-conversation"
  facts: KeyFact[]              // extracted facts at this point
  notes: string[]               // free-form observations
  selfCard: SelfCard | null     // which self this branch explores (null for root)
  createdAt: number
}
```

### Branches
A branch is just a pointer to the latest node on a path (exactly like git).
```
MemoryBranch {
  name: string                  // e.g. "the-architect", "the-wanderer"
  headNodeId: string            // points to the latest MemoryNode on this branch
  parentBranchName: string | null  // which branch this forked from
}
```

### HEAD
The session has a `HEAD` pointer that tracks which branch is currently active — which future self the user is currently talking to.

### Backtracking (Checkout)
When the user wants to explore a different future self:
1. The current branch's head is updated with the latest facts
2. HEAD moves to the new branch (or a new branch is created from the root/fork point)
3. The conversation engine loads the memory facts from the new branch's path (root → ... → head)
4. The transcript records the backtrack as a new event (nothing is deleted)
5. Previous branch is fully preserved — user can return to it anytime

### Memory Resolution (Walking the Tree)
When the conversation engine needs the current memory context, it **walks from root to HEAD**, collecting all facts along the path:
```python
def resolve_memory(head_node_id):
    """Walk from head to root, collect all facts in path order."""
    facts = []
    node = get_node(head_node_id)
    while node:
        facts = node.facts + facts  # prepend so root facts come first
        node = get_node(node.parent_id) if node.parent_id else None
    return facts
```

This means:
- Root facts (from the profile/interview) are always included
- Branch-specific facts are only included when on that branch
- Sub-branch facts layer on top of their parent branch's facts

## Storage Structure (Files)

```
storage/
  sessions/
    {session_id}/
      session.json              # session metadata (status, selected self, HEAD)
      transcript.json           # linear log, append-only
      memory/
        nodes/
          {node_id}.json        # individual memory nodes
        branches.json           # branch name → head node mapping
      avatars/
        {self_id}.png           # cached generated avatar images
```

Each session is now a **directory** (not a single file), because the memory tree can grow and we want to read/write nodes independently.

## Interaction with Backend
- `SessionStore` manages the full session directory
- `MemoryTree` class handles branch/node operations:
  - `create_branch(name, parent_node_id, self_card)` — fork a new branch
  - `commit(branch_name, facts, notes)` — add a node to a branch
  - `checkout(branch_name)` — move HEAD to a different branch
  - `resolve(branch_name)` — walk the tree and return all facts from root to head
  - `get_branches()` — list all branches with their head summaries
- Routers call `MemoryTree` through `SessionStore`, engines never access storage directly

## Interaction with Conversation Engine
The ConversationEngine receives resolved memory (flat list of facts from root to HEAD). It doesn't know about the tree structure — it just sees "here are the relevant facts for this conversation." The tree management happens at the router/session level.

## TODO
- [ ] Create MemoryNode and MemoryBranch Pydantic models
- [ ] Create MemoryTree class with branch/commit/checkout/resolve operations
- [ ] Update SessionStore to manage session directories instead of single files
- [ ] Implement transcript as append-only JSON array
- [ ] Implement avatar image caching in session directory
- [ ] Create backtrack endpoint that handles branch switching
- [ ] Write tests for tree traversal and memory resolution
- [ ] Ensure atomic writes for node creation
