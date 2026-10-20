# Privacy and publication boundaries

The public repository contains source, English documentation, a credential-free
configuration example, and synthetic tests. Local settings, subjects, results,
logs, reports, environments, archives, and backups are excluded.

Ignoring files does not sanitize their contents. The audit checks tracked and
non-ignored new files, so accidentally tracked private artifacts are rejected.
Pass an external JSON array of known private identifiers to --private-denylist.
Never commit it. Generic checks also flag common key formats, non-example email
addresses, machine paths, and private artifacts. Inspect unfamiliar binaries.

The Git audit scans blobs, commits, tags, paths, and metadata, including unreachable
objects and reflogs. Replacing history does not delete other clones, forks, caches,
or backups. Checks cover the new snapshot and its history.

Research and cloud inference are outbound operations. Logs and results may contain
subjects, context, sources, and generated content. Email sends to the configured
recipient when requested. Do not publish local records. Keep the app on loopback.
