import hashlib
from pathlib import Path
import unittest


SKILLS_PATH = Path(__file__).resolve().parents[1] / "skills"
SHARED_RUNTIME_SKILL_NAMES = ("document", "pdf", "spreadsheet", "presentation", "dataroom", "paperwork")


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill_files():
    return sorted(path for path in SKILLS_PATH.rglob("*") if path.is_file())


class SharedSkillRuntimeTest(unittest.TestCase):
    def test_every_bundled_runtime_is_the_same_file(self):
        digests = {
            skill_name: file_digest(SKILLS_PATH / skill_name / "scripts" / "skill_runtime.py")
            for skill_name in SHARED_RUNTIME_SKILL_NAMES
        }
        self.assertEqual(len(set(digests.values())), 1, f"skill_runtime.py copies diverged: {digests}")


class HostNeutralEnvironmentTest(unittest.TestCase):
    def test_no_skill_names_its_host(self):
        offending_paths = [
            str(path.relative_to(SKILLS_PATH))
            for path in skill_files()
            if b"BLUECLAW_" in path.read_bytes()
        ]
        self.assertEqual(offending_paths, [], "skills must read environment variables no host owns")


if __name__ == "__main__":
    unittest.main()
