"""Audit every local Git object and repository metadata, including unreachable objects.

Reports contain object IDs and categories, never matched values or historical paths.
Use PUBLIC_PRIVACY_DENYLIST or --private-denylist for an external private reference list.
Ignored working files and copies on other machines are outside this audit.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from audit_public import ROOT, load_identity, private_path, text_findings


def audit_history(root=ROOT, denylist_path=None):
    root = Path(root).resolve()
    git = ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root)]
    identity = load_identity(root, denylist_path)
    findings = []
    counts = Counter()
    trees = {}
    explicit_roots = set()
    hash_size = 32 if subprocess.check_output(git + ["rev-parse", "--show-object-format"]).strip() == b"sha256" else 20

    def inspect(label, data):
        encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        findings.extend({"object": label, **item}
                        for item in text_findings(data.decode(encoding, errors="replace"), identity))

    # --batch-all-objects includes loose, packed and unreachable objects.
    process = subprocess.Popen(git + ["cat-file", "--batch-all-objects", "--batch"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        while header := process.stdout.readline():
            oid, kind, size = header.decode("ascii").split()
            data = process.stdout.read(int(size))
            if len(data) != int(size) or process.stdout.read(1) != b"\n":
                raise ValueError("Incomplete Git object stream.")
            counts[kind] += 1
            if kind != "tree":
                inspect(oid, data)
                if kind == "commit":
                    explicit_roots.add(data.splitlines()[0].split(b" ", 1)[1].decode("ascii"))
                elif kind == "tag" and b"\ntype tree\n" in data:
                    explicit_roots.add(data.splitlines()[0].split(b" ", 1)[1].decode("ascii"))
                continue
            entries = []
            position = 0
            while position < len(data):
                end = data.index(b"\0", position)
                mode, name = data[position:end].split(b" ", 1)
                child = data[end + 1:end + 1 + hash_size].hex()
                entries.append((mode, name.decode("utf-8", errors="replace"), child))
                position = end + 1 + hash_size
            trees[oid] = entries
        process.stderr.read()
        if process.wait():
            raise RuntimeError("Git object enumeration failed; the audit is incomplete.")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()

    visited = set()

    def inspect_tree(oid, prefix=""):
        if (oid, prefix) in visited:
            return
        visited.add((oid, prefix))
        for mode, name, child in trees.get(oid, []):
            relative = prefix + name
            inspect(oid, relative.encode("utf-8"))
            if mode == b"40000":
                inspect_tree(child, relative + "/")
            else:
                if private_path(relative):
                    findings.append({"object": oid, "line": 0, "category": "private-artifact"})
                if mode in (b"120000", b"160000"):
                    findings.append({"object": oid, "line": 0, "category": "external-link"})

    # Preserve full paths: frontend/src/data is source, while root data is private.
    # Orphaned tree roots are included even if no commit points to them.
    nested_trees = {child for entries in trees.values()
                    for mode, name, child in entries if mode == b"40000"}
    tree_refs = subprocess.check_output(git + ["for-each-ref", "--format=%(objectname)"],
                                       text=True).splitlines()
    explicit_roots.update(oid for oid in tree_refs if oid in trees)
    for oid in (set(trees) - nested_trees) | explicit_roots:
        inspect_tree(oid)

    metadata_count = 0
    metadata_dirs = {
        Path(subprocess.check_output(git + ["rev-parse", "--path-format=absolute", flag],
                                     text=True).strip())
        for flag in ("--git-dir", "--git-common-dir")
    }
    for git_dir in metadata_dirs:
        for path in git_dir.rglob("*"):
            relative = path.relative_to(git_dir)
            if relative.parts[0] == "objects" or not path.is_file():
                continue
            label = "metadata:" + hashlib.sha256(relative.as_posix().encode()).hexdigest()[:12]
            inspect(label, relative.as_posix().encode())
            inspect(label, path.read_bytes())
            metadata_count += 1
        alternates = git_dir / "objects/info/alternates"
        if alternates.exists():
            findings.append({"object": "metadata:alternates", "line": 0, "category": "external-object-store"})

    integrity = subprocess.run(git + ["fsck", "--full", "--no-reflogs", "--unreachable"],
                               capture_output=True)
    if integrity.returncode:
        findings.append({"object": "repository", "line": 0, "category": "git-integrity-error"})
    unreachable_count = sum(line.startswith(b"unreachable ")
                            for line in integrity.stdout.splitlines())
    return {
        "scope": "all local Git objects, paths, refs, reflogs, config and index",
        "private_denylist_loaded": identity is not None,
        "objects_checked": sum(counts.values()),
        "object_types": dict(counts),
        "metadata_files_checked": metadata_count,
        "unreachable_objects": unreachable_count,
        "finding_count": len(findings),
        "categories": dict(Counter(item["category"] for item in findings)),
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-denylist", type=Path)
    parser.add_argument("--json", type=Path, help="Write a redacted audit report.")
    args = parser.parse_args()
    report = audit_history(denylist_path=args.private_denylist)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f'Checked {report["objects_checked"]} Git objects and '
          f'{report["metadata_files_checked"]} metadata files; {report["finding_count"]} findings.')
    for item in report["findings"]:
        print(f'{item["object"]}:{item["line"]}: {item["category"]}')
    return int(bool(report["findings"]))


if __name__ == "__main__":
    sys.exit(main())
