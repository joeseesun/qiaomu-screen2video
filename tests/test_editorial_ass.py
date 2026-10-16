import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import editorial_ass as ea


def ffmpeg_with_ass():
    for c in ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", shutil.which("ffmpeg")):
        if c and Path(c).exists():
            out = subprocess.run([c, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
            if " ass " in out:
                return c
    return None


class EasingTests(unittest.TestCase):
    def test_expo_is_monotonic_and_lands_on_one(self):
        vals = [ea.ease_out_expo(i / 20) for i in range(21)]
        self.assertTrue(all(b >= a for a, b in zip(vals, vals[1:])))
        self.assertEqual(vals[-1], 1.0)
        self.assertGreaterEqual(vals[2], 0.5)     # fast attack: half done within the first 10%
        self.assertGreater(vals[3], 0.6)

    def test_spring_overshoot_is_small(self):
        peak = max(ea.ease_out_spring(i / 100) for i in range(100))
        self.assertGreater(peak, 1.0)
        self.assertLess(peak, 1.06)

    def test_exit_is_slow_then_fast(self):
        self.assertLess(ea.ease_in_cubic(0.3), 0.05)
        self.assertEqual(ea.ease_in_cubic(1.0), 1.0)


class DrawingTests(unittest.TestCase):
    def test_circle_path_is_positive_only(self):
        self.assertNotIn("-", ea.circle(6))    # negative coordinates drift under \an5

    def test_rounded_rect_closes_at_origin_edge(self):
        p = ea.rounded_rect(100, 50, 10)
        self.assertTrue(p.startswith("m 10 0"))
        self.assertTrue(p.endswith("10 0"))


class KaraokeTests(unittest.TestCase):
    def test_durations_and_gap(self):
        t = ea.karaoke_line([("你", 0.08, 0.30), ("好", 0.30, 0.52)])
        self.assertEqual(t, "{\\k8}{\\kf22}你{\\kf22}好")


class PaletteTests(unittest.TestCase):
    def test_hex_to_bgr(self):
        self.assertEqual(ea.palette_from_hex("#F05A3C").accent_dark, "&H3C5AF0&")

    def test_accent_follows_palette_not_hardcoded(self):
        a = ea.Ass(palette="mono-vermilion")
        ea.chapter_progress(a, [0, 5, 10], ["一", "二"], 200, 1400, t_end=10)
        ea.detached_card(a, 1, 3.8, 240, 52, "01 / 02", "标题", "说明")
        out = a.render()
        self.assertIn("3C5AF0", out)
        self.assertNotIn("FF9132", out)       # the default blue must not leak into another look

    def test_every_preset_has_one_accent_distinct_from_neutrals(self):
        for name, p in ea.PALETTES.items():
            self.assertNotEqual(p.accent_dark, p.hair, name)


class AssTests(unittest.TestCase):
    def test_text_rises_and_fades(self):
        a = ea.Ass()
        a.add(1.0, 3.0, "Sub", "{\\fad(70,70)\\pos(960,912)}你好")
        self.assertGreater(len(a.events), 3)
        first = a.events[0]
        self.assertIn("\\pos(960.0,", first)
        self.assertTrue(any("\\fad(0,70)" in e for e in a.events))   # fade-out survives
        # eased: y approaches the final position
        ys = [float(e.split("\\pos(960.0,")[1].split(")")[0]) for e in a.events if "\\pos(960.0," in e]
        self.assertGreater(ys[0], ys[-1])
        self.assertEqual(ys[-1], 912.0)

    def test_short_cues_skip_rise(self):
        a = ea.Ass()
        a.add(0, 0.2, "Sub", "{\\fad(70,70)\\pos(960,912)}x")
        self.assertEqual(len(a.events), 1)

    def test_progress_has_a_dot_per_chapter_and_centred_dot(self):
        a = ea.Ass()
        ea.chapter_progress(a, [3, 20, 40, 60], ["一", "二", "三"], 200, 1500, t_end=60)
        dots = [e for e in a.events if "\\move(" in e]
        self.assertEqual(len(dots), 3)
        self.assertTrue(all("\\an7" in e for e in dots))   # \an7 + positive path = exactly centred

    def test_card_never_translucent_body(self):
        a = ea.Ass()
        ea.detached_card(a, 1, 3.8, 240, 52, "01 / 06", "听文章", "任何一篇文章，一键念出来")
        body = [e for e in a.events if "&H0A0A0A&" in e]
        self.assertTrue(body)
        mid = body[len(body) // 2]
        self.assertIn("\\1a&H00&", mid)

    def test_render_has_header_and_styles(self):
        s = ea.Ass().render()
        self.assertIn("PlayResX: 1920", s)
        self.assertIn("Style: Karaoke,", s)

    @unittest.skipUnless(ffmpeg_with_ass(), "ffmpeg with libass not available")
    def test_real_render_draws_pixels(self):
        ff = ffmpeg_with_ass()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = ea.Ass()
            a.add(0.2, 2.5, "Sub", "{\\fad(70,70)\\pos(960,912)}你好，世界")
            ea.chapter_progress(a, [0.0, 1.5, 3.0], ["一", "二"], 217, 1486, t_end=3.0)
            (d / "t.ass").write_text(a.render())
            r = subprocess.run([ff, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=3840x2160:r=30:d=3",
                                "-vf", f"ass={d}/t.ass", "-frames:v", "1", "-ss", "1", str(d / "f.png")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertGreater((d / "f.png").stat().st_size, 5000)   # something was drawn on black


if __name__ == "__main__":
    unittest.main()
