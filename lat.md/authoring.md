# Authoring

`rpa-authoring/` holds UiPath Studio sources used as design/prototype inputs for
Python Flow packages.

It is not a runtime dependency of Client, Task, or Engine. There is no automated
XAML→Python translator in this tree.

## UiPath Login Demo

The current artifact is `uipath/login_demo`: a Windows UiPath process that opens
Chrome, drives a demo portal login, and maps captcha images to codes.

Key files: `project.json` / `project.uiproj`, `Main.xaml`, `entry-points.json`.
Selectors use `data-rpa` attributes aligned with the Playwright port
`rpa_flow_login_demo` under [[flow-packages]].

## Relationship To Runtime

Author in UiPath → hand-port to a versioned package in `rpa-flows/` → publish and
execute via [[rpa-engine]].

Keep Studio caches (`.local/`, `.settings/`) out of product runtime paths. New
authoring projects should land under `rpa-authoring/`, never inside `app/` or
`service/`.
