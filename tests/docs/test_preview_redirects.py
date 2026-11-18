"""Retired Preview routes preserve the destination and visitor's URL state."""
import importlib.util
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import unittest

SPEC = importlib.util.spec_from_file_location("redirect_publisher", Path(__file__).parents[2] / "doc/scripts/build_versioned_docs.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class PreviewRedirects(unittest.TestCase):
    def test_redirects_use_latest_pages(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            catalogue = {"versions": {
                "latest": {"url": "https://example.test/latest/", "documents": {"index": [], "guide/analysis": []}},
                "model_gallery": {"url": "https://example.test/model_gallery/", "documents": {"index": [], "models/pv": []}},
            }}
            publisher.write_preview_redirects(root, catalogue)
            aliases = root / 'en/preview'
            self.assertEqual({p.relative_to(aliases).as_posix() for p in aliases.rglob("*") if p.is_file()},
                             {"index.html", "guide/analysis.html"})
            for document in ("index", "guide/analysis"):
                page = (aliases / (document + ".html")).read_text()
                target = f"https://example.test/latest/{document}.html"
                self.assertIn('href="' + target + '"', page)
                self.assertIn('content="0;url=' + target + '"', page)
                self.assertIn('name="robots" content="noindex"', page)
                script = re.search(r"<script>(.*?)</script>", page).group(1)
                # Execute the delivered redirect, including encoded indicator state and an anchor.
                result = subprocess.check_output(["node", "-e",
                    'global.location={search:"?indicator=ghg&country=C%26D",hash:"#motor-vehicles",'
                    'replace:target=>process.stdout.write(target)};' + script], text=True)
                self.assertEqual(result, target + "?indicator=ghg&country=C%26D#motor-vehicles")
            self.assertEqual(set(catalogue["versions"]), {"latest", "model_gallery"})
