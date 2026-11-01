extends SceneTree
## Repeatable, real renderer measurements. Snapshots are immutable Python output.
const Scene = preload("res://native_scene.gd")
var samples: Array = []
var measuring = false
var last_frame_usec = 0

func _initialize():
    run.call_deferred()

func _process(_delta):
    var now = Time.get_ticks_usec()
    if measuring and last_frame_usec > 0: samples.append((now - last_frame_usec) * .001)
    last_frame_usec = now
    return false

func require(ok, message):
    if not ok:
        push_error(message)
        quit(1)

func run():
    var args = OS.get_cmdline_user_args()
    require(args.size() >= 4, "Expected assets, fixture, output directory, quality")
    if args.size() < 4: return
    var fixture = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
    var output = args[2]
    var profile = args[3]
    Engine.max_fps = 0
    DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
    var scene = Scene.new()
    root.add_child(scene)
    scene.setup(args[0], profile)
    scene.effects.audio_enabled = false
    scene.cinematic_effects = false
    scene.set_process_unhandled_input(false)
    var reports = []
    for item in fixture.views:
        scene.asset_choice = item.asset
        scene.model_key = ""
        scene.set_snapshot(item.snapshot)
        scene.azimuth = deg_to_rad(item.camera.azimuth_deg)
        scene.elevation = deg_to_rad(item.camera.elevation_deg)
        scene.distance = item.camera.distance_m
        scene.focus_height = item.camera.focus_height_m
        scene.camera.fov = item.camera.fov_deg
        scene.environment.tonemap_exposure = item.camera.exposure
        scene.camera.attributes.auto_exposure_enabled = false
        scene.camera.attributes.dof_blur_far_enabled = false
        scene.camera.attributes.dof_blur_near_enabled = false
        scene.vehicle_root.visible = item.id != "earth-terminator"
        scene.target_root.visible = false
        for i in range(90): await process_frame
        await create_timer(2.0).timeout
        require(scene.last_model_import_ok, "Asset failed: " + item.id + " " + scene.asset_error)
        samples.clear()
        measuring = true
        var start_usec = Time.get_ticks_usec()
        while samples.size() < 150 or Time.get_ticks_usec() - start_usec < 2000000: await process_frame
        measuring = false
        samples.sort()
        var total = 0.0
        for ms in samples: total += ms
        var mean = total / max(1, samples.size())
        await RenderingServer.frame_post_draw
        var capture = output.path_join(item.id + ".png")
        require(root.get_texture().get_image().save_png(capture) == OK, "Capture failed: " + capture)
        var report = {
            "id": item.id, "samples": samples.size(), "mean_frame_ms": mean,
            "fps": 1000.0 / mean, "p50_frame_ms": samples[int(samples.size() * .5)],
            "p95_frame_ms": samples[int(samples.size() * .95)], "max_frame_ms": samples[-1],
            "draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
            "primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
            "capture": capture, "asset": scene.active_asset_id, "camera": item.camera,
            "actual_camera_m": [scene.camera.position.x, scene.camera.position.y, scene.camera.position.z],
            "simulation_time_s": item.snapshot.state.time_s,
            "terrain_chunks": scene.terrain_stream.chunks.size() if is_instance_valid(scene.terrain_stream) else 0
        }
        reports.append(report)
        print("CAPTURE ", item.id, " ", profile, " ", snappedf(report.fps, .1), " FPS")
    # Isolated sky witness removes planets/vehicles and temporal AA. Its pixels
    # detect accidental changes to the protected nebula and star background.
    scene.set_process(false)
    scene.world_root.visible = false
    scene.vehicle_root.visible = false
    scene.target_root.visible = false
    scene.sky_material.set_shader_parameter("planet_visible", false)
    scene.sky_material.set_shader_parameter("companion_visible", false)
    RenderingServer.global_shader_parameter_set("atmosphere", 0.0)
    root.use_taa = false
    root.msaa_3d = Viewport.MSAA_DISABLED
    root.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
    root.scaling_3d_scale = 1.0
    scene.camera.position = Vector3.ZERO
    scene.camera.rotation = Vector3(.12, .65, 0)
    scene.environment.tonemap_exposure = 1.0
    scene.environment.glow_enabled = false
    for i in range(12): await process_frame
    await RenderingServer.frame_post_draw
    require(root.get_texture().get_image().save_png(output.path_join("protected-sky.png")) == OK, "Sky capture failed")
    var result = {
        "quality": profile, "renderer": RenderingServer.get_current_rendering_method(),
        "adapter": RenderingServer.get_video_adapter_name(), "resolution": [root.size.x, root.size.y],
        "vsync": false, "fps_cap": 0, "measurement": "At least 150 raw wall-clock frames and two seconds per fixed view, after 90 frames plus two seconds warmup",
        "views": reports, "protected_sky": output.path_join("protected-sky.png")
    }
    var file = FileAccess.open(output.path_join("report.json"), FileAccess.WRITE)
    file.store_string(JSON.stringify(result, "  "))
    scene.queue_free()
    await process_frame
    quit(0)
