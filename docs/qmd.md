# Optional QMD

QMD can improve retrieval and duplicate detection, but it is not required.

Start with `qmd_sync: off`. The Librarian may use an available QMD installation for read-only duplicate preflight. Enable `update` or `update_and_embed` only after you understand the collections and local hooks that your QMD configuration runs.

Never point QMD at Librarian proposal or receipt directories. Index only the canonical Markdown vault.

