"""通用 Flow 包构建器：打包 + 与 Engine 上传 API 相同的策略校验。

用法（在 rpa-engine 目录下运行，保证 nodeskclaw_rpa_engine 可导入）：

    $env:PYTHONPATH = "src"
    .\\.venv\\Scripts\\python.exe ..\\rpa-flows\\scripts\\build_flow_package.py `
      --flow-dir ..\\rpa-flows\\rpa_flow_srm_scan_pending_orders\\1.0.0
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from nodeskclaw_rpa_engine.core.config import Settings
from nodeskclaw_rpa_engine.flows.package import FlowPackageValidator, PackageLimits

FLOW_FILES = ("manifest.json", "selectors.json", "flow.py")
PACKAGE_TIMESTAMP = (2026, 8, 13, 0, 0, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and validate a Flow ZIP package")
    parser.add_argument("--flow-dir", type=Path, required=True, help="Flow version source directory")
    parser.add_argument("--output", type=Path, help="Custom ZIP path (default: <flow-dir>/../dist)")
    args = parser.parse_args()

    source = args.flow_dir.resolve()
    manifest = source / "manifest.json"
    if not manifest.is_file():
        raise FileNotFoundError(f"manifest.json missing in {source}")

    import json

    meta = json.loads(manifest.read_text(encoding="utf-8"))
    flow_id = meta["rpaFlowId"]
    version = meta["version"]
    output = (
        args.output.resolve()
        if args.output is not None
        else source.parents[1] / "dist" / f"{flow_id}-{version}.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FLOW_FILES:
            source_file = source / name
            if not source_file.is_file():
                raise FileNotFoundError(f"Flow source file is missing: {source_file}")
            entry = zipfile.ZipInfo(name, date_time=PACKAGE_TIMESTAMP)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 0
            entry.external_attr = 0o100666 << 16
            archive.writestr(entry, source_file.read_bytes())

    settings = Settings(_env_file=None, app_env="test")
    validator = FlowPackageValidator(
        PackageLimits(
            max_bytes=settings.flow_package_max_bytes,
            max_uncompressed_bytes=settings.flow_package_max_uncompressed_bytes,
            max_files=settings.flow_package_max_files,
            max_compression_ratio=settings.flow_package_max_compression_ratio,
        )
    )
    package = validator.validate(output.name, output.read_bytes())
    print(f"package={output}")
    print(f"sha256={package.checksum_sha256}")
    print(f"size={package.size_bytes}")


if __name__ == "__main__":
    main()
