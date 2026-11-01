"""Render real native mission/SAS UI from recorded, actually executed API calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare_fixture(path):
    from desktop_runtime import DesktopRuntime

    # Keep the user's career and active desktop entirely untouched.
    career_path = path.parent / f"isolated-career-{time.time_ns()}.json"
    with patch.object(DesktopRuntime, "_career_file", staticmethod(lambda: career_path)):
        runtime = DesktopRuntime()
        runtime.dispatch("/desktop/free", dict(vehicle="space", scenario="orbital", advanced_models=True), "POST")
        runtime.dispatch("/command", dict(mode="manual", sas_enabled=True), "POST")
        sas = runtime.dispatch("/desktop/snapshot")
        mission_id = "proc1:space_lunar_precision:0"
        runtime.dispatch("/desktop/game/start", dict(mission_id=mission_id, language="it"), "POST")
        runtime.dispatch("/command", dict(mode="auto"), "POST")
        runtime.dispatch("/launch", {}, "POST")
        steps = 0
        for _ in range(600):
            runtime.dispatch("/step", dict(dt_s=.5), "POST")
            steps += 1
            progress = runtime.game_session.snapshot()
            if progress.get("complete") or progress.get("failed"):
                break
        success = runtime.dispatch("/desktop/snapshot")
        assert success["game"]["complete"] and not success["game"].get("failed"), success["game"]
        assert success["state"]["time_s"] > 0 and success["state"]["phase"] == "LANDED"
        responses = []
        base = dict(vehicle="space", language="it", query="", offset=0, limit=10,
                    source="all", difficulty=0, max_duration_s=0, family="", sort="difficulty")
        difficulty_total = search_total = 0
        search_query = "Luna"
        for query in [base, dict(base, source="contracts"), dict(base, offset=10), dict(base, difficulty=1), dict(base, difficulty=1, query=search_query)]:
            response = runtime.dispatch("/desktop/game/catalog", query, "POST")
            responses.append(dict(endpoint="/desktop/game/catalog", payload=query, response=response))
            if query["difficulty"] == 1:
                if query["query"]:
                    search_total = response["_meta"]["total"]
                else:
                    difficulty_total = response["_meta"]["total"]
        fixture = dict(schema=1, provenance="Unmodified DesktopRuntime.dispatch responses; real engine integration; isolated career",
                       sas=sas, success=success, steps=steps, dt_s=.5, models=runtime.dispatch("/models"),
                       responses=responses, difficulty_total=difficulty_total, search_total=search_total,
                       search_query=search_query)
        path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true", help="Exercise native layouts/filters without a GPU capture")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "test-results/mission-ui")
    parser.add_argument("--renderer", type=Path, default=ROOT / "build/toolchain/godot/Godot_v4.7.2-stable_win64.exe")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / "fixture.json"
    prepare_fixture(fixture)
    project = output / "project"
    shutil.copytree(ROOT / "desktop", project, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".godot"))
    config = (project / "project.godot").read_text(encoding="utf-8")
    config = config.replace("[rendering]", "[rendering]\nshader_compiler/shader_cache/enabled=false")
    (project / "project.godot").write_text(config, encoding="utf-8")
    log_path = output / "godot.log"
    log_path.write_text("", encoding="utf-8")
    command = [str(args.renderer.resolve()), "--path", str(project), "--script", str(ROOT / "tools/capture_mission_ui.gd"),
               "--position", "-10000,-10000", "--resolution", "1440x900", "--rendering-method", "forward_plus",
               "--log-file", str(log_path)]
    if args.headless:
        command.append("--headless")
    command += ["--", str(ROOT / "assets"), str(fixture), str(output)]
    with (output / "process.log").open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        try:
            deadline = time.monotonic() + 120
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError("Native mission UI capture timed out")
                text = log_path.read_text(encoding="utf-8", errors="replace")
                if "SCRIPT ERROR:" in text or "\nERROR:" in text:
                    raise AssertionError(text[-6000:])
                time.sleep(.2)
            assert process.returncode == 0, (output / "process.log").read_text(encoding="utf-8")[-6000:]
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(15)
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    report["fixture_sha256"] = hashlib.sha256(fixture.read_bytes()).hexdigest()
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.publish and not args.headless:
        for filename in ("sas-hud.png", "mission-board.png", "mission-result.png"):
            shutil.copy2(output / filename, ROOT / "docs/images" / filename)
        shutil.copy2(output / "report.json", ROOT / "docs/validation/mission-ui.json")
    print(json.dumps({key:value for key,value in report.items() if key != "result"}, indent=2))


if __name__ == "__main__":
    main()
