"""Capture identical Python states/cameras and benchmark the actual Godot GPU.

Run --phase before once, then --phase after after renderer changes. The fixture
is reused verbatim; this tool never connects to or modifies an active flight.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_sky_digest():
    shader = (ROOT / "desktop/sky.gdshader").read_text(encoding="utf-8")
    stars = shader.split("float star_layer", 1)[1].split("vec3 planet_background", 1)[0]
    background = shader.split("void sky()", 1)[1]
    return hashlib.sha256((stars + background).encode("utf-8")).hexdigest()


def prepare_fixture(path):
    from astra.engine import SimulationEngine
    from desktop_runtime import visual_frame

    views = []
    for identifier, vehicle, scenario, seconds, asset, camera in [
        ("orbit", "space", "orbital", 10, "nasa-orion-spacecraft", (55, 18, 13, 0, 48, .8)),
        ("earth-terminator", "space", "orbital", 10, "nasa-orion-spacecraft", (125, 36, 18000000, -6700000, 48, 1.0)),
        ("moon-descent", "space", "planetary", 35, "auto", (55, 12, 13, 1.7, 48, 1.0)),
        ("aircraft", "aircraft", "mission", 90, "auto", (135, 12, 23, 1.2, 48, .9)),
        ("drone", "drone", "mission", 30, "auto", (55, 16, 2.3, .2, 48, .9)),
    ]:
        engine = SimulationEngine()
        engine.reset(vehicle, scenario, advanced_models=True)
        engine.launch()
        for _ in range(seconds * 10):
            state = engine.step(.1)
        assert state["phase"] not in {"CRASHED", "ABORTED"}, (identifier, state["phase"])
        snap = dict(state=copy.deepcopy(state), visual=visual_frame(state), desktop=dict(running=False, clock_owner="desktop"))
        names = ("azimuth_deg", "elevation_deg", "distance_m", "focus_height_m", "fov_deg", "exposure")
        views.append(dict(id=identifier, asset=asset, snapshot=snap, camera=dict(zip(names, camera))))
    path.write_text(json.dumps(dict(schema=1, source="SimulationEngine; actual integrated SI states; no presentation edits to physics", views=views), indent=2), encoding="utf-8")


def run_capture(renderer, fixture, output, quality):
    output.mkdir(parents=True, exist_ok=True)
    # Stage identical sources so benchmarking never touches a running editor's
    # config. Disable disk shader cache only in this measurement project: user://
    # is outside the workspace sandbox. Warm up all pipelines before sampling.
    project = output / "project"
    shutil.copytree(ROOT / "desktop", project, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".godot"))
    configuration = (project / "project.godot").read_text(encoding="utf-8")
    configuration = configuration.replace("[rendering]", "[rendering]\nshader_compiler/shader_cache/enabled=false")
    (project / "project.godot").write_text(configuration, encoding="utf-8")
    command = [str(renderer), "--path", str(project), "--script", str(ROOT / "tools/capture_upgrade.gd"),
               "--position", "-10000,-10000", "--resolution", "1440x900",
               "--rendering-method", "gl_compatibility" if quality == "low" else "forward_plus",
               "--log-file", str(output / "godot.log"), "--", str(ROOT / "assets"), str(fixture), str(output), quality]
    (output / "godot.log").write_text("", encoding="utf-8")
    with (output / "process.log").open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        try:
            deadline = time.monotonic() + 240
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Graphics measurement timed out: {quality}")
                log = output / "godot.log"
                text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
                # Compatibility 4.7 still probes user:// even when disk caching
                # is disabled. Retain that known sandbox warning in the log;
                # every shader/script/render error remains fatal.
                checked = text.replace("ERROR: Can't create shader cache folder, no shader caching will happen: user://", "CACHE UNAVAILABLE: user://")
                if "SCRIPT ERROR:" in checked or "\nERROR:" in checked:
                    raise AssertionError(text[-5000:])
                time.sleep(.2)
            assert process.returncode == 0, (output / "process.log").read_text(encoding="utf-8")[-5000:]
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(15)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert len(report["views"]) == 5
    assert all(row["samples"] >= 100 and row["fps"] > 0 for row in report["views"])
    report.update(fixture_sha256=digest(fixture), renderer_sha256=digest(renderer),
                  sky_shader_sha256=digest(ROOT / "desktop/sky.gdshader"),
                  protected_sky_source_sha256=protected_sky_digest(),
                  protected_sky_png_sha256=digest(output / "protected-sky.png"),
                  capture_script_sha256=digest(ROOT / "tools/capture_upgrade.gd"), disk_shader_cache=False)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["before", "after"], required=True)
    parser.add_argument("--qualities", nargs="+", default=["low", "balanced", "high", "ultra"])
    parser.add_argument("--renderer", type=Path, default=ROOT / "build/toolchain/godot/Godot_v4.7.2-stable_win64.exe")
    parser.add_argument("--output", type=Path, default=ROOT / "test-results/graphics-upgrade")
    parser.add_argument("--publish", action="store_true", help="Copy High captures and reports into docs for review")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / "fixtures.json"
    if not fixture.exists():
        if args.phase == "after":
            raise ValueError("Capture the baseline before renderer changes first")
        prepare_fixture(fixture)
    reports = []
    for quality in args.qualities:
        directory = output / args.phase / quality
        if args.phase == "before" and (directory / "report.json").exists():
            report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
            assert report["fixture_sha256"] == digest(fixture)
            print("Reusing immutable baseline", quality, flush=True)
        else:
            print("Measuring", args.phase, quality, flush=True)
            report = run_capture(args.renderer.resolve(), fixture, directory, quality)
        if args.phase == "after":
            baseline = output / "before" / quality / "report.json"
            if baseline.exists():
                before = json.loads(baseline.read_text(encoding="utf-8"))
                assert before["fixture_sha256"] == report["fixture_sha256"], "Before/after physics fixture differs"
                assert before["renderer_sha256"] == report["renderer_sha256"], "Before/after Godot binary differs"
                assert before["protected_sky_source_sha256"] == report["protected_sky_source_sha256"], "Protected stars/nebula source changed"
                report["protected_sky_identical_pixels"] = before["protected_sky_png_sha256"] == report["protected_sky_png_sha256"]
                assert report["protected_sky_identical_pixels"], "Protected sky capture changed"
                for old, new in zip(before["views"], report["views"]):
                    assert old["id"] == new["id"] and old["camera"] == new["camera"]
                    assert old["simulation_time_s"] == new["simulation_time_s"]
                    assert max(abs(a-b) for a,b in zip(old["actual_camera_m"], new["actual_camera_m"])) < max(.001, max(abs(x) for x in old["actual_camera_m"]) * 1e-6), "Camera mismatch beyond floating-point scale tolerance"
                (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        reports.append(report)
        print(quality, [(r["id"], round(r["fps"], 1), round(r["p95_frame_ms"], 1)) for r in report["views"]], flush=True)
        if args.publish:
            destination = ROOT / "docs/validation/graphics-upgrade"
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(directory / "report.json", destination / f"{args.phase}-{quality}.json")
            if quality == "high":
                images = ROOT / "docs/images/graphics-upgrade"
                images.mkdir(parents=True, exist_ok=True)
                for image in directory.glob("*.png"):
                    shutil.copy2(image, images / f"{args.phase}-{image.name}")
    summary = dict(phase=args.phase, fixture_sha256=digest(fixture), reports=reports)
    (output / f"{args.phase}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
