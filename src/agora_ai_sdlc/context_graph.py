"""Deterministic context graph over persisted linked artifacts.

Pure functions over files: no vector store, no network, no provider. Nodes are artifacts plus the Bolts inside
`bolt-plan` artifacts (addressed as ``BLP-001/api``). Edges point backward from an artifact to the sources it
traces to; forward traversal is the inverse relation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from agora_ai_sdlc.artifacts import PREFIX, SCHEMA, Artifact, ArtifactError, parse_artifact, split
from agora_ai_sdlc.bolts import BoltError, parse_bolt_plan

DIRECTIONS = ("backward", "forward", "both")
KIND_ORDER = {kind: index for index, kind in enumerate(PREFIX)}
BOLT_KIND = "bolt"


class ContextError(ValueError):
    """Stable context-assembly failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def estimate_tokens(text: str) -> int:
    """Deterministic, provider-neutral token estimate (about four characters per token)."""

    return math.ceil(len(text) / 4)


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    path: str
    text: str
    tokens: int
    sources: tuple[str, ...]  # backward edges, in declaration order


@dataclass(frozen=True)
class Graph:
    nodes: dict[str, Node]
    dangling: tuple[tuple[str, str], ...]  # (node, missing target), sorted

    def sources(self, node_id: str) -> tuple[str, ...]:
        return tuple(s for s in self.nodes[node_id].sources if s in self.nodes)

    def derived(self) -> dict[str, tuple[str, ...]]:
        inverse: dict[str, list[str]] = {node_id: [] for node_id in self.nodes}
        for node_id in sorted(self.nodes):
            for source in self.sources(node_id):
                inverse[source].append(node_id)
        return {node_id: tuple(items) for node_id, items in inverse.items()}


@dataclass(frozen=True)
class ContextItem:
    id: str
    kind: str
    path: str
    distance: int
    relation: str  # root | backward | forward
    tokens: int


@dataclass(frozen=True)
class ContextBundle:
    root: str
    direction: str
    items: tuple[ContextItem, ...]
    omitted: tuple[str, ...]
    dangling: tuple[tuple[str, str], ...]
    cycles: tuple[tuple[str, ...], ...]
    total_tokens: int
    text: dict[str, str] = field(default_factory=dict, compare=False)

    def snapshot(self, *, include_text: bool = False) -> dict:
        data = {
            "root": self.root,
            "direction": self.direction,
            "items": [
                {
                    "id": i.id,
                    "kind": i.kind,
                    "path": i.path,
                    "distance": i.distance,
                    "relation": i.relation,
                    "tokens": i.tokens,
                }
                for i in self.items
            ],
            "omitted": list(self.omitted),
            "dangling": [list(pair) for pair in self.dangling],
            "cycles": [list(cycle) for cycle in self.cycles],
            "total_tokens": self.total_tokens,
        }
        if include_text:
            data["text"] = {item.id: self.text[item.id] for item in self.items}
        return data


def load_artifacts(root: Path) -> list[tuple[Path, str, Artifact]]:
    """Parse every artifact document under root (sorted); non-artifact Markdown is ignored."""

    found = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            front, _ = split(text)
        except ArtifactError:
            continue
        if front.get("schema") != SCHEMA:
            continue
        try:
            found.append((path, text, parse_artifact(text)))
        except ArtifactError as error:
            raise ContextError("context.artifact", f"{path}: {error}") from error
    return found


def build_graph(documents: list[tuple[Path | str, str, Artifact]], *, base: Path | None = None) -> Graph:
    nodes: dict[str, Node] = {}
    bolt_sources: dict[str, list[str]] = {}  # produced artifact id -> producing bolt node ids

    def rel(path: Path | str) -> str:
        if base is not None and isinstance(path, Path):
            try:
                return path.relative_to(base).as_posix()
            except ValueError:
                pass
        return str(path)

    for path, text, artifact in documents:
        if artifact.id in nodes:
            raise ContextError("context.duplicate_id", f"duplicate artifact id {artifact.id}")
        nodes[artifact.id] = Node(
            artifact.id, artifact.kind, rel(path), text, estimate_tokens(text), artifact.traces_to
        )
        if artifact.kind != "bolt-plan":
            continue
        try:
            plan = parse_bolt_plan(text)
        except BoltError as error:
            raise ContextError("context.bolt_plan", f"{artifact.id}: {error}") from error
        for bolt in plan.bolts:
            bolt_id = f"{artifact.id}/{bolt.id}"
            body = (
                f"{bolt_id} [{bolt.mode}, {bolt.status}]\n"
                + "\n".join(f"- {task}" for task in bolt.tasks)
                + f"\nwrites: {', '.join(bolt.writes) or '-'}\nevidence: {', '.join(bolt.evidence) or '-'}\n"
            )
            deps = tuple(f"{artifact.id}/{dep}" for dep in bolt.depends_on)
            nodes[bolt_id] = Node(bolt_id, BOLT_KIND, rel(path), body, estimate_tokens(body), (artifact.id, *deps))
            for produced in bolt.produces:
                bolt_sources.setdefault(produced, []).append(bolt_id)

    for produced, bolt_ids in bolt_sources.items():
        node = nodes.get(produced)
        if node is not None:
            merged = tuple(dict.fromkeys((*node.sources, *bolt_ids)))
            nodes[produced] = Node(node.id, node.kind, node.path, node.text, node.tokens, merged)

    dangling = sorted({(node.id, target) for node in nodes.values() for target in node.sources if target not in nodes})
    return Graph(nodes, tuple(dangling))


def graph_from_directory(root: Path) -> Graph:
    return build_graph(load_artifacts(root), base=root)


def find_cycles(graph: Graph) -> tuple[tuple[str, ...], ...]:
    """Strongly connected groups of size > 1 (or self-loops) in the trace relation, sorted."""

    reach: dict[str, set[str]] = {}
    for node_id in graph.nodes:
        seen: set[str] = set()
        stack = list(graph.sources(node_id))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(graph.sources(current))
        reach[node_id] = seen
    groups = {
        tuple(sorted({node_id} | {other for other in reach[node_id] if node_id in reach[other]}))
        for node_id in graph.nodes
        if node_id in reach[node_id]
    }
    return tuple(sorted(groups))


def _walk(graph: Graph, root: str, step) -> dict[str, int]:
    distance = {root: 0}
    frontier = [root]
    while frontier:
        nxt = []
        for node_id in frontier:
            for neighbour in step(node_id):
                if neighbour not in distance:
                    distance[neighbour] = distance[node_id] + 1
                    nxt.append(neighbour)
        frontier = nxt
    return distance


def context_bundle(
    graph: Graph,
    root: str,
    *,
    direction: str = "both",
    max_depth: int | None = None,
    max_tokens: int | None = None,
    strict: bool = False,
) -> ContextBundle:
    """Minimal deterministic context for an Intent, Unit, artifact or Bolt (``BLP-001/api``).

    Backward and forward traversals are independent, so siblings and unrelated branches are never pulled in.
    Items are ordered by distance, backward before forward, kind order, then id. The root is always kept;
    other items are added in order while they fit `max_tokens` (a larger item is skipped, not truncated).
    """

    if direction not in DIRECTIONS:
        raise ContextError("context.direction", f"direction must be one of {', '.join(DIRECTIONS)}")
    if root not in graph.nodes:
        raise ContextError("context.unknown_root", f"unknown artifact or bolt {root!r}")
    if max_depth is not None and max_depth < 0:
        raise ContextError("context.depth", "max_depth must be >= 0")
    if max_tokens is not None and max_tokens < 1:
        raise ContextError("context.budget", "max_tokens must be >= 1")

    derived = graph.derived()
    candidates: dict[str, tuple[int, int]] = {root: (0, 0)}  # id -> (distance, relation rank)
    for rank, wanted, step in ((1, "backward", graph.sources), (2, "forward", lambda n: derived[n])):
        if direction not in (wanted, "both"):
            continue
        for node_id, dist in _walk(graph, root, step).items():
            if node_id == root or (max_depth is not None and dist > max_depth):
                continue
            if node_id not in candidates or (dist, rank) < candidates[node_id]:
                candidates[node_id] = (dist, rank)

    names = {0: "root", 1: "backward", 2: "forward"}
    ordered = sorted(
        candidates,
        key=lambda i: (candidates[i][0], candidates[i][1], KIND_ORDER.get(graph.nodes[i].kind, 99), i),
    )
    items: list[ContextItem] = []
    omitted: list[str] = []
    total = 0
    for node_id in ordered:
        node = graph.nodes[node_id]
        if node_id != root and max_tokens is not None and total + node.tokens > max_tokens:
            omitted.append(node_id)
            continue
        dist, rank = candidates[node_id]
        items.append(ContextItem(node_id, node.kind, node.path, dist, names[rank], node.tokens))
        total += node.tokens

    selected = {item.id for item in items} | set(omitted)
    dangling = tuple(pair for pair in graph.dangling if pair[0] in selected)
    if strict and dangling:
        first = dangling[0]
        raise ContextError("context.dangling", f"{first[0]} traces to unknown {first[1]}")
    cycles = tuple(cycle for cycle in find_cycles(graph) if selected & set(cycle))
    if strict and cycles:
        raise ContextError("context.cycle", f"trace cycle among {', '.join(cycles[0])}")
    return ContextBundle(
        root,
        direction,
        tuple(items),
        tuple(omitted),
        dangling,
        cycles,
        total,
        {i.id: graph.nodes[i.id].text for i in items},
    )
