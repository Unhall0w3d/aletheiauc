"""Sequential SSH trust preflight and bounded node collection helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Protocol, TypeVar

from cisco_collab_health.models.runtime import CollectionContext


T = TypeVar("T")


class SshSession(Protocol):
    def __enter__(self) -> "SshSession": ...
    def __exit__(self, *_: object) -> None: ...


SessionFactory = Callable[[CollectionContext], SshSession]


def preflight_ssh_nodes(
    context: CollectionContext,
    nodes: Iterable[str],
    session_factory: SessionFactory,
) -> tuple[list[CollectionContext], list[str]]:
    """Open and close every node serially, allowing one key prompt at a time."""

    ready: list[CollectionContext] = []
    warnings: list[str] = []
    for node in dict.fromkeys(item for item in nodes if item):
        node_context = replace(context, target=node, publisher_ip=node)
        try:
            with session_factory(node_context):
                pass
        except Exception as exc:
            warnings.append(f"SSH preflight failed on {node}: {exc}")
        else:
            # The worker pool must never prompt or enroll a key. It uses the
            # key just validated and saved by this serial preflight instead.
            ready.append(
                replace(node_context, accept_new_host_key=False, host_key_approval=None)
            )
    return ready, warnings


def collect_preflighted_nodes(
    contexts: Iterable[CollectionContext],
    workers: int,
    collect_one: Callable[[CollectionContext], T],
) -> list[T]:
    """Collect independent nodes concurrently while preserving input result order."""

    ordered_contexts = list(contexts)
    if len(ordered_contexts) < 2 or workers <= 1:
        return [collect_one(context) for context in ordered_contexts]
    with ThreadPoolExecutor(max_workers=min(workers, len(ordered_contexts))) as executor:
        futures = [executor.submit(collect_one, context) for context in ordered_contexts]
        return [future.result() for future in futures]
