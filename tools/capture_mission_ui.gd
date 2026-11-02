extends SceneTree
## Replay exact local API responses for repeatable native UI evidence.
const Main = preload("res://main.gd")
const NativeScene = preload("res://native_scene.gd")
const Board = preload("res://mission_board.gd")

class RecordedMain extends Main:
    var fixture = {}
    var active_snapshot = {}
    var requests_seen = []
    func _ready(): pass
    func _process(_delta):
        if widgets.has("render"):
            widgets.render.text="%s · %d FPS · %s"%[RenderingServer.get_current_rendering_method().to_upper(),Engine.get_frames_per_second(),quality.to_upper()]
    func same_payload(left, right):
        if left == null or right == null: return left == right
        if left.size() != right.size(): return false
        for key in left:
            if not right.has(key): return false
            if (left[key] is float or left[key] is int) and (right[key] is float or right[key] is int):
                if not is_equal_approx(float(left[key]),float(right[key])): return false
            elif left[key] != right[key]: return false
        return true
    func request(endpoint, payload=null):
        requests_seen.append({"endpoint":endpoint,"payload":payload})
        if endpoint == "/desktop/snapshot": return active_snapshot.duplicate(true)
        for row in fixture.responses:
            if endpoint == row.endpoint and same_payload(payload,row.payload):
                return row.response.duplicate(true)
        push_error("Unrecorded UI request: " + endpoint + " " + JSON.stringify(payload))
        return {"error":"Unrecorded request"}

func _initialize(): run.call_deferred()

func require(ok, message):
    if not ok:
        push_error(message)
        quit(1)
    return ok

func capture(path):
    for i in range(30): await process_frame
    await create_timer(1.1).timeout
    if DisplayServer.get_name() == "headless": return
    await RenderingServer.frame_post_draw
    require(root.get_texture().get_image().save_png(path) == OK, "Could not save " + path)

func run():
    var args = OS.get_cmdline_user_args()
    if not require(args.size() >= 3, "Expected assets, fixture, output"): return
    var fixture = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
    if not require(fixture.success.game.complete, "Result fixture must be a completed real flight"): return
    root.gui_embed_subwindows = true
    Engine.max_fps = 0
    var app = RecordedMain.new()
    app.fixture = fixture
    root.add_child(app)
    app.asset_path = args[0]
    app.models = fixture.models
    app.studies = JSON.parse_string(FileAccess.get_file_as_string("res://studies.json"))
    app.catalog = JSON.parse_string(FileAccess.get_file_as_string("res://vehicles.json"))
    app.scene = NativeScene.new()
    app.add_child(app.scene)
    app.scene.setup(args[0], "high")
    app.scene.effects.audio_enabled = false
    app.make_interface()
    app.configure_controller_ui()
    app.active_snapshot = fixture.sas
    await app.poll()
    app.scene.distance = 16
    app.scene.azimuth = .8
    if not require(app.sas_hud.visible and app.sas_hud.toggle_button.text.contains("ON"), "SAS HUD missing"): return
    if not require(app.sas_hud.mode_buttons.maneuver_node.disabled, "Invalid node mode displayed"): return
    await create_timer(1.1).timeout
    app.update_hud()
    await capture(args[2].path_join("sas-hud.png"))

    if fixture.has("launch_sas"):
        app.active_snapshot=fixture.launch_sas
        await app.poll()
        if not require(not app.sas_hud.mode_buttons.normal.disabled and not app.sas_hud.mode_buttons.prograde.disabled,"Launch SAS modes unavailable"):return
        app.scene.distance=45;app.scene.azimuth=.8
        await capture(args[2].path_join("launch-sas-hud.png"))
    app.active_snapshot = fixture.success
    app.game_result_seen = str(fixture.success.game.mission.id)
    await app.poll()
    app.game_mode = true
    app.game_career = fixture.success.career
    var board = Board.new()
    board.setup(app, "space", "it")
    await process_frame
    if not require(board.total >= 300 and board.rows_box.get_child_count() == 10, "Board not populated/paged"): return
    var first_id = board.selected_id
    board.query_widgets.source.select(2)
    board.query_widgets.source.item_selected.emit(2)
    await process_frame
    if not require(board.total >= 300 and board.selected_id.begins_with("proc1:"), "Procedural contracts filter failed"): return
    await capture(args[2].path_join("mission-board.png"))
    board.query_widgets.source.select(0)
    board.query_widgets.source.item_selected.emit(0)
    await process_frame
    board.next_button.pressed.emit()
    await process_frame
    if not require(board.offset == 10 and board.selected_id != first_id and board.rows_box.get_child_count() == 10, "Next page did not change missions"): return
    board.query_widgets.difficulty.select(1)
    board.query_widgets.difficulty.item_selected.emit(1)
    await process_frame
    if not require(board.offset == 0 and board.total == int(fixture.difficulty_total), "Difficulty filtering failed"): return
    board.query_widgets.query.text = fixture.search_query
    board.offset = 0
    board.refresh()
    await process_frame
    if not require(board.total == int(fixture.search_total), "Search filtering failed"): return
    board.queue_free()
    await process_frame
    app.update_hud()
    app.show_game_result()
    await capture(args[2].path_join("mission-result.png"))
    var results = {"board_population":true,"pagination":true,"difficulty_filter":true,"search_filter":true,
        "sas_hud":true,"real_completed_mission":fixture.success.game.mission.id,
        "physical_time_s":fixture.success.state.time_s,"result":fixture.success.game,
        "renderer":RenderingServer.get_current_rendering_method(),"adapter":RenderingServer.get_video_adapter_name(),
        "headless":DisplayServer.get_name() == "headless","request_count":app.requests_seen.size()}
    var report = FileAccess.open(args[2].path_join("report.json"), FileAccess.WRITE)
    report.store_string(JSON.stringify(results,"  "))
    print("MISSION UI PASS: real completion, board, paging, filters, SAS")
    app.queue_free()
    await process_frame
    quit(0)
