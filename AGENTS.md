# project-memory bootstrap pointer

Discovery bridge only; canonical project truth remains in the files named by `docs/CONTINUITY.md`.
When this repository is selected by the MCF registry, treat this checkout as TARGET_REPOSITORY_ROOT. Resolve `.mcf/project-capsule.yaml` and all project canonical entrypoints from this root.
Before any write or implementation, read `docs/CONTINUITY.md`, `.mcf/project-capsule.yaml`, and `docs/NEXT.md`, then resolve and apply the MCF canonical operating instructions. For continuation, use `snapshot.next_action` together with the first unfinished numbered priority in `docs/NEXT.md`. Do not skip to a later priority unless a canonical source explicitly marks it independent/executable while the earlier priority remains open. If bootstrap is incomplete or sources conflict, perform discovery only and do not modify files.
