"""Create an audited source-only ZIP without rewriting executable code."""
from __future__ import annotations
import argparse
from datetime import datetime
from pathlib import Path
import sys
import zipfile
from scripts.audit_public import ROOT, audit, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--private-denylist", type=Path)
    args = parser.parse_args()
    report = audit(denylist_path=args.private_denylist)
    if report["finding_count"]:
        print(f"Export refused: {report['finding_count']} privacy findings. Run scripts/audit_public.py for locations.")
        return 1
    output = args.output or ROOT / "dist" / f"Paradigme-{datetime.now():%Y%m%d-%H%M%S}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in candidates():
            path = ROOT / relative
            if path.is_file():
                archive.write(path, "Paradigme/" + relative)
    print(f"Exported {report['files_checked']} source files to {output.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
