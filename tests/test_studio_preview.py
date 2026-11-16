import os
import struct
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path
import unittest

from test_studio import fixture
from reeltern.preview import GRADE_META, PreviewEngine, clip_at_time, fit_monitor_box
from reeltern.studio import Studio


def _parse_ppm(ppm_bytes):
    header_end = 0
    newlines = 0
    for idx, b in enumerate(ppm_bytes):
        if b == 10:
            newlines += 1
            if newlines == 3:
                header_end = idx + 1
                break
    header = ppm_bytes[:header_end].decode('ascii').splitlines()
    assert header[0] == 'P6', header
    w, h = (int(v) for v in header[1].split())
    assert int(header[2]) == 255
    pixels = ppm_bytes[header_end:]
    assert len(pixels) == w * h * 3
    return w, h, pixels


def _pixel_at(pixels, w, x, y):
    off = (y * w + x) * 3
    return struct.unpack_from('BBB', pixels, off)


class PreviewEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.media = Path(cls.shared.name)
        cls.video = fixture(cls.media, 'speech.mp4', audio=True)

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def test_fit_monitor_box_and_clip_at_time(self):
        lw, lh = fit_monitor_box('landscape', 540, 340)
        self.assertEqual((lw % 2, lh % 2), (0, 0))
        self.assertGreater(lw, lh)

        pw, ph = fit_monitor_box('portrait', 540, 340)
        self.assertEqual((pw % 2, ph % 2), (0, 0))
        self.assertGreater(ph, pw)

        sw, sh = fit_monitor_box('square', 300, 300)
        self.assertEqual(sw, sh)

        plan = {
            'clips': [
                {'asset_id': 'a', 'start': 0.0, 'end': 2.0, 'speed': 1.0, 'timeline_start': 0.0, 'frames': 60},
                {'asset_id': 'b', 'start': 1.0, 'end': 3.0, 'speed': 2.0, 'timeline_start': 2.0, 'frames': 30},
            ]
        }
        r0 = clip_at_time(plan, 0.5)
        self.assertEqual(r0[0], 0)
        self.assertAlmostEqual(r0[2], 0.5, places=3)

        r1 = clip_at_time(plan, 2.5)
        self.assertEqual(r1[0], 1)
        self.assertAlmostEqual(r1[2], 2.0, places=3)

    def test_live_effects_blur_fill_noir_fade_and_thumbnail(self):
        engine = PreviewEngine()
        try:
            self.assertEqual(len(GRADE_META), 10)

            bw, bh, blur_ppm = engine.render_clip_frame(
                self.video, 0.4, 240, 260, preset='portrait', fit='blur_fill',
                clip={'grade': 'none', 'brightness': 0.0, 'contrast': 1.0, 'saturation': 1.0},
            )
            cw, ch, contain_ppm = engine.render_clip_frame(
                self.video, 0.4, 240, 260, preset='portrait', fit='contain',
                clip={'grade': 'none', 'brightness': 0.0, 'contrast': 1.0, 'saturation': 1.0},
            )
            self.assertEqual((bw, bh), (cw, ch))
            self.assertGreater(bh, bw)
            _, _, blur_px = _parse_ppm(blur_ppm)
            _, _, contain_px = _parse_ppm(contain_ppm)
            self.assertNotEqual(_pixel_at(blur_px, bw, bw // 2, 10), _pixel_at(contain_px, cw, cw // 2, 10))

            nw, nh, noir_ppm = engine.render_clip_frame(
                self.video, 0.4, 260, 160, preset='landscape', fit='contain',
                clip={'grade': 'noir', 'brightness': 0.0, 'contrast': 1.0, 'saturation': 1.0},
            )
            _, _, noir_px = _parse_ppm(noir_ppm)
            for sx in (nw // 4, nw // 2, (3 * nw) // 4):
                r, g, b = _pixel_at(noir_px, nw, sx, nh // 2)
                self.assertEqual(r, g)
                self.assertEqual(g, b)

            fw, fh, fade_ppm = engine.render_clip_frame(
                self.video, 0.4, 260, 160, preset='landscape', fit='contain',
                clip={'grade': 'none', 'fade_in': 1.0}, local_time=0.0, clip_duration=2.0,
            )
            _, _, fade_px = _parse_ppm(fade_ppm)
            self.assertEqual(_pixel_at(fade_px, fw, fw // 2, fh // 2), (0, 0, 0))

            tw, th, thumb_ppm = engine.render_thumbnail(self.video, 0.25, thumb_w=84, thumb_h=48)
            self.assertEqual((tw, th), (84, 48))
            _parse_ppm(thumb_ppm)
        finally:
            engine.close()
        self.assertEqual(len(engine.containers), 0)
        self.assertEqual(len(engine.frames), 0)


class StudioWorkstationUXTests(unittest.TestCase):
    @staticmethod
    def _pump_until(root, app, predicate, timeout=25.0):
        headless_macos_ci = sys.platform == 'darwin' and bool(os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if headless_macos_ci:
                if getattr(app, '_poll_after', None) is not None:
                    try:
                        root.after_cancel(app._poll_after)
                    except tk.TclError:
                        pass
                    app._poll_after = None
                app.poll()
                if getattr(app, '_monitor_after', None) is not None:
                    try:
                        root.after_cancel(app._monitor_after)
                    except tk.TclError:
                        pass
                    app._monitor_after = None
                    app._refresh_monitor_now()
            else:
                root.update()
            if predicate():
                return True
            time.sleep(0.03)
        return False

    def test_studio_workstation_live_monitor_director_grade_trim_and_qa(self):
        try:
            root = tk.Tk()
        except (tk.TclError, RuntimeError) as exc:
            self.skipTest(f'Tk display unavailable: {exc}')
        root.withdraw()

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        app = Studio(root, Path(temp.name) / 'studio-ux')
        try:
            self._pump_until(root, app, lambda: True, timeout=0.05)

            app.load_demo()
            self.assertTrue(
                self._pump_until(root, app, lambda: (not app.busy) and app.plan is not None, timeout=25.0),
                app.status.get(),
            )
            app._refresh_monitor_now()
            self.assertIsNotNone(app.monitor_photo)
            self.assertGreater(len(app.timeline.get_children()), 0)

            app._switch_tab('director')
            app._select_director_style('cinematic')
            self.assertEqual(app.selected_director.get(), 'cinematic')
            app._compose_selected_director()
            self.assertTrue(
                self._pump_until(root, app, lambda: (not app.busy) and app.plan and app.plan.get('preset') == 'landscape', timeout=15.0),
                app.status.get(),
            )

            app._switch_tab('look')
            app._pick_grade('teal_orange')
            self.assertEqual(app.fx_fields['grade'].get(), 'teal_orange')
            app.apply_clip_effects()
            self.assertEqual(app.plan['clips'][0]['grade'], 'teal_orange')

            app._switch_tab('trim')
            orig_start = float(app.plan['clips'][0]['start'])
            orig_end = float(app.plan['clips'][0]['end'])
            app._seek_playhead(0.4)
            app.mark_in_at_playhead()
            new_start = float(app.plan['clips'][0]['start'])
            self.assertGreater(new_start, orig_start)

            app._seek_playhead(max(0.2, float(app.plan['clips'][0]['frames']) / 30.0 - 0.3))
            app.mark_out_at_playhead()
            self.assertLessEqual(float(app.plan['clips'][0]['end']), orig_end)

            app.undo()
            self.assertAlmostEqual(float(app.plan['clips'][0]['start']), new_start, places=2)

            app.start_render(preview=True)
            self.assertIsNotNone(app.job)
            self.assertTrue(
                self._pump_until(root, app, lambda: app.btn_mode_render.cget('state') == 'normal', timeout=30.0),
                app.status.get(),
            )
            self.assertEqual(app.monitor_mode.get(), 'rendered')
            app._refresh_monitor_now()
            self.assertIsNotNone(app.monitor_photo)

            app.audit_render()
            self.assertTrue(
                self._pump_until(root, app, lambda: (not app.busy) and app.tile_black.val_var.get() != '—', timeout=20.0),
                app.status.get(),
            )
            self.assertNotEqual(app.tile_luma.val_var.get(), '—')
            self.assertNotEqual(app.tile_lufs.val_var.get(), '—')
            summary = app.qa_summary_var.get()
            self.assertTrue(summary.startswith('PASSED') or summary.startswith('NEEDS REVIEW'), summary)
        finally:
            app._cleanup_resources()
            try:
                root.destroy()
            except tk.TclError:
                pass
