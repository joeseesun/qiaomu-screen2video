"""Public installs must work without the author's other personal skills."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_outro_assets_without_sibling_profile_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'qiaomu-screen2video'
            (package / 'scripts').mkdir(parents=True)
            script = package / 'scripts/outro_compose.py'
            shutil.copy2(ROOT / 'scripts/outro_compose.py', script)
            shutil.copytree(ROOT / 'assets/qiaomu-profile', package / 'assets/qiaomu-profile')
            self.assertFalse((package.parent / 'qiaomu-profile').exists())
            spec = importlib.util.spec_from_file_location('isolated_outro', script)
            outro = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(outro)
            avatar = outro.avatar(64)
            self.assertEqual(avatar.size, (64, 64))
            self.assertEqual(avatar.getpixel((0, 0))[3], 0)
            self.assertGreater(avatar.getpixel((32, 32))[3], 0)
            self.assertEqual(outro.qr(48).size, (48, 48))
