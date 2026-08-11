# AutoTask Workspace Agent Notes

## Required Startup Context

- This workspace contains multiple AutoTask projects. Treat each project directory as an independent ownership boundary.
- Before project work, read `D:\AutoTask-Workspace\project-docs\PROJECT_CONTROL.md`, including the latest `Daily Development Log` entry.
- Update the control file after verified work changes project status, decisions, blockers, paths, or next actions.
- Never record passwords, tokens, database credentials, private keys, or signed object-storage URLs.

## Project Map

Allowed **project code** roots for agent scanning and edits (only these five):

- Client: `copilot-autotask/`
- Task service: `nodeskclaw/nodeskclaw-task/`
- RPA Engine: `nodeskclaw-rpa-engine/`
- RPA Flow packages: `rpa-flows/`
- RPA authoring (UiPath etc.): `rpa-authoring/`

Product records and designs (not a code root; read/update for control): `project-docs/`

Do not place Engine code, Flow packages, UiPath projects, Task service code, or product-wide records inside the Client repository. Do not scan other `nodeskclaw/*` packages unless the user explicitly requests a named path.

## Windows And Chinese Text Encoding

- Chinese documentation and JSON data use UTF-8 without BOM.
- In Windows PowerShell, read Chinese files explicitly with `Get-Content -Encoding utf8`.
- Before inspecting many Chinese files, set console output to UTF-8 when useful.
- Re-read mojibake with explicit UTF-8 before editing; do not assume the source is corrupt.
- Keep manually written files in UTF-8 and do not change encodings without an explicit requirement.

## Database Hold Point

- Database designs and dormant DDL may be prepared.
- Do not create a database, schema, role, extension, table, migration record, or seed data.
- Do not execute bootstrap, DDL, verification, or write SQL until the user explicitly authorizes database execution.

