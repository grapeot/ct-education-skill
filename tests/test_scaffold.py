import fnmatch
import os
from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {
    "workspace", "workspaces", "data", "input", "output", "artifacts", "private"
}
LOCAL_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
SUFFIXES = (
    "dcm dicom ima nii nii.gz nrrd nhdr mha mhd raw img hdr npy npz h5 hdf5 "
    "pkl pickle pt pth onnx safetensors bin pdf png jpg jpeg tif tiff webp gif "
    "bmp glb gltf obj stl ply vtk vtp blend blend1 mp4 mov avi webm mkv zip tar "
    "gz bz2 xz 7z"
).split()
ALLOWED_NAMES = {"LICENSE", ".gitignore", ".env.example", ".gitkeep"}
PRIVATE_TEXT = re.compile(
    r"/(?:Users|home)/[A-Za-z0-9_.-]+/"
    r"|op:" + r"//"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?:sk|ghp|github_pat)[_-][A-Za-z0-9_\-]{20,}"
    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)


def hygiene_findings(root):
    findings = set()
    for directory, subdirs, files in os.walk(root, followlinks=False):
        for name in subdirs[:]:
            path = Path(directory) / name
            if path.is_symlink():
                findings.add("symlink")
                subdirs.remove(name)
            elif name.lower() in PRIVATE_DIRS:
                findings.add("private-directory")
                subdirs.remove(name)
            elif name in LOCAL_DIRS:
                subdirs.remove(name)
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                findings.add("symlink")
                continue
            if name.lower() == "dicomdir" or any(
                name.lower().endswith("." + suffix) for suffix in SUFFIXES
            ):
                findings.add("asset-suffix")
                continue
            if name not in ALLOWED_NAMES and path.suffix not in {".md", ".py", ".yml"}:
                findings.add("unexpected-file")
                continue
            if path.stat().st_size > 256_000:
                findings.add("oversized-file")
                continue
            content = path.read_bytes()
            if any(byte not in (9, 10, 13) and not 32 <= byte <= 126 for byte in content):
                findings.add("non-ascii-or-binary")
                continue
            if PRIVATE_TEXT.search(content.decode("ascii")):
                findings.add("private-text")
    return findings


class ScaffoldTests(unittest.TestCase):
    def test_required_layout_and_single_skill(self):
        required = {
            "README.md", "AGENTS.md", "LICENSE", ".gitignore", ".env.example",
            "docs/prd.md", "docs/rfc.md", "docs/test.md", "docs/working.md",
            "skills/ct_education.md", "src/.gitkeep", "scripts/.gitkeep",
            "tests/test_scaffold.py", ".github/workflows/ci.yml",
        }
        self.assertTrue(all((ROOT / name).is_file() for name in required))
        self.assertEqual(
            sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "skills").rglob("*") if path.is_file()),
            ["skills/ct_education.md"],
        )
        skill = (ROOT / "skills/ct_education.md").read_text()
        self.assertTrue(skill.startswith("---\nname: ct-education\ndescription:"))
        self.assertIn("Scaffold only", skill)

    def test_public_file_hygiene(self):
        self.assertEqual(hygiene_findings(ROOT), set())

    def test_ignore_declarations(self):
        rules = (ROOT / ".gitignore").read_text().splitlines()
        for name in PRIVATE_DIRS:
            self.assertIn(name + "/", rules)
        for rule in (".env", ".env.*", "!.env.example", ".venv/", "logs/", "*.log"):
            self.assertIn(rule, rules)
        # This checks declared basename patterns, not Git's full ignore semantics.
        for suffix in SUFFIXES:
            for name in ("probe." + suffix, "probe." + suffix.upper()):
                self.assertTrue(any(fnmatch.fnmatchcase(name, rule) for rule in rules))
        self.assertTrue(any(fnmatch.fnmatchcase("DICOMDIR", rule) for rule in rules))

    def test_fake_configuration_and_license(self):
        self.assertEqual(
            (ROOT / ".env.example").read_text(),
            "CT_EDU_WORKSPACE=/path/to/external/workspace\n",
        )
        license_text = (ROOT / "LICENSE").read_text()
        self.assertIn("Copyright (c) 2026 CT Education Skill contributors", license_text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', license_text)

    def test_ci_policy_declarations(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertEqual(workflow.count("branches: [master]"), 2)
        for declaration in (
            "  push:", "  pull_request:", "  scaffold-hygiene:",
            "  contents: read", "persist-credentials: false",
            "python -B -m unittest discover -s tests -v",
        ):
            self.assertIn(declaration, workflow)
        for prohibited in ("pull_request_target:", "upload-artifact", "deploy", "secrets."):
            self.assertNotIn(prohibited, workflow)

    def test_scanner_rejects_private_directories_and_asset_names(self):
        with self.external_scratch() as directory:
            root = Path(directory)
            for name in PRIVATE_DIRS:
                (root / "nested" / name).mkdir(parents=True, exist_ok=True)
            for suffix in SUFFIXES:
                (root / ("probe." + suffix.upper())).touch()
            self.assertEqual(hygiene_findings(root), {"private-directory", "asset-suffix"})

    def test_scanner_rejects_binary_in_text_file(self):
        with self.external_scratch() as directory:
            root = Path(directory)
            (root / "probe.md").write_bytes(b"synthetic\x00probe")
            self.assertEqual(hygiene_findings(root), {"non-ascii-or-binary"})

    def test_scanner_rejects_symlinks_without_following(self):
        with self.external_scratch() as directory:
            root = Path(directory)
            (root / "probe.md").symlink_to(root / "missing")
            self.assertEqual(hygiene_findings(root), {"symlink"})

    def test_scanner_rejects_generic_private_markers(self):
        with self.external_scratch() as directory:
            root = Path(directory)
            for marker in (
                "/" + "home" + "/example/local/",
                "op:" + "//example/item/field",
                "ghp" + "_" + "x" * 24,
                "example" + "@" + "example.invalid",
            ):
                (root / "probe.md").write_text(marker)
                self.assertEqual(hygiene_findings(root), {"private-text"})

    def external_scratch(self):
        base = Path(tempfile.gettempdir()).resolve()
        if base == ROOT or ROOT in base.parents:
            self.fail("external-temp-required")
        return tempfile.TemporaryDirectory(prefix="ct-edu-hygiene-", dir=base)


if __name__ == "__main__":
    unittest.main()
