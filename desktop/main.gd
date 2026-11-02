extends Node

const SceneClass = preload("res://native_scene.gd")
const InputClass = preload("res://native_input.gd")
const MenuWindow = preload("res://menu_window.gd")
const SasHUD = preload("res://sas_hud.gd")
const MissionBoard = preload("res://mission_board.gd")
const MissionMap = preload("res://mission_map.gd")
var api_url = "http://127.0.0.1:8765"
var asset_path = ""
var quality = "balanced"
var smoke_path = ""
var scene
var pilot = InputClass.new()
var ui
var state = {}
var desktop = {}
var models = {}
var catalog = {}
var studies = {}
var widgets = {}
var pending = false
var elapsed = 0.0
var pilot_elapsed = 0.0
var pilot_pending = false
var latest_pilot_command = {}
var pilot_error = ""
var pilot_rtt_ms = 0.0
const PILOT_SEND_PERIOD = 1.0/60.0
var keyboard_active = false
var keyboard_throttle = 0.0
var keyboard_target = Vector3.ZERO
var vehicle = "space"
var scenario = "mission"
var custom_design = null
var model_selection
var visual_selection
var mission_selection
var sas_selection
var sas_hud
var sas_request_pending=false
var controller_learn_axis=""
var controller_learn_editor
var controller_learn_baseline=[]
var mode_selection
var game_mode=false
var game_state={}
var game_career={}
var game_result_seen=""
var game_language="it"
var game_language_loaded=false
var mission_messages={}
var advanced
var result_view
var laboratory
var sample_history = []
var career = {"track":"pilot","xp":0,"missions":0,"observations":0}
var awarded = false
var replay_samples = []
var replay_index = -1
var renderer_frames = 0
var frame_times = []
var start_wall = 0
var smoke_suite_path = ""
var last_science_update_ms = 0
var reset_pending = false
var seen_revision = -1
var view_revision=-1
var view_settings={}
var view_changed_keys=[]
var render_elapsed=0.0
var render_pending=false
var capture_busy=false
var captures_seen={}
var free_mode=false
var details=[]
var detail_widgets={}
var last_detail_update=0
var validation_mode=false
var python_proof_path=""
var python_proof_data=""
var python_proof_started=false

func _ready():
    configure_controller_ui()
    var arguments = OS.get_cmdline_user_args()
    var polish_path=""
    var polish_fixtures=""
    for i in range(arguments.size()-1):
        match arguments[i]:
            "--api":api_url=arguments[i+1]
            "--assets":asset_path=arguments[i+1]
            "--quality":quality=arguments[i+1]
            "--smoke":smoke_path=arguments[i+1]
            "--smoke-suite":smoke_suite_path=arguments[i+1]
            "--polish-check":polish_path=arguments[i+1]
            "--polish-fixtures":polish_fixtures=arguments[i+1]
            "--python-proof":python_proof_path=arguments[i+1]
            "--python-proof-data":python_proof_data=arguments[i+1]
    if polish_path!="":
        validation_mode=true
        var runner=load("res://polish_validation.gd").new();add_child(runner)
        runner.run.call_deferred(asset_path,polish_fixtures,polish_path,quality)
        return
    if quality=="auto":quality="balanced"
    Engine.max_fps=0
    DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
    scene = SceneClass.new()
    add_child(scene)
    scene.setup(asset_path,quality)
    studies = JSON.parse_string(FileAccess.get_file_as_string("res://studies.json"))
    var config = ConfigFile.new()
    if config.load("user://career.cfg")==OK:
        for key in career:career[key]=config.get_value("career",key,career[key])
    make_interface()
    start_wall = Time.get_ticks_msec()
    Input.joy_connection_changed.connect(joy_connection)
    bootstrap()

func request(endpoint,payload=null):
    var http = HTTPRequest.new()
    add_child(http)
    http.timeout = 90
    var method = HTTPClient.METHOD_GET if payload==null else HTTPClient.METHOD_POST
    var body = "" if payload==null else JSON.stringify(payload)
    var error = http.request(api_url+"/api/v1"+endpoint,["Content-Type: application/json"],method,body)
    if error!=OK:
        http.queue_free()
        return {"error":"API non disponibile · "+str(error)}
    var reply = await http.request_completed
    http.queue_free()
    if reply[0]!=HTTPRequest.RESULT_SUCCESS:
        return {"error":"Connessione API interrotta · "+str(reply[0])}
    var parsed = JSON.parse_string(reply[3].get_string_from_utf8())
    if parsed==null:return {"error":"Risposta API non valida"}
    return parsed

func bootstrap():
    models = await request("/models")
    var file = FileAccess.open(asset_path.path_join("vehicle-models.json"),FileAccess.READ)
    if file!=null:catalog=JSON.parse_string(file.get_as_text())
    fill_models()
    # The host owns the initial state; attaching graphics must never reset a
    # mission that an already connected Python controller has configured.
    await poll()
    if smoke_suite_path!="":smoke_suite()

func label_text(text,size=14,color=Color(.75,.83,.92)):
    var node = Label.new()
    node.text=text
    node.add_theme_font_size_override("font_size",size)
    node.add_theme_color_override("font_color",color)
    return node

func button(text,callback,parent):
    var b = Button.new()
    b.text=text
    b.custom_minimum_size.y=36
    b.pressed.connect(callback)
    parent.add_child(b)
    return b

func panel(parent,position,size):
    var p = PanelContainer.new()
    p.position=position
    p.size=size
    var style = StyleBoxFlat.new()
    style.bg_color=Color(.025,.047,.08,.95)
    style.border_color=Color(.23,.36,.5,.55)
    style.set_border_width_all(1)
    style.set_corner_radius_all(8)
    style.content_margin_left=18
    style.content_margin_right=18
    style.content_margin_top=16
    style.content_margin_bottom=16
    p.add_theme_stylebox_override("panel",style)
    parent.add_child(p)
    return p

func make_interface():
    mission_messages=JSON.parse_string(FileAccess.get_file_as_string("res://mission_i18n.json"))
    var layer = CanvasLayer.new()
    add_child(layer)
    ui = Control.new()
    ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    ui.mouse_filter=Control.MOUSE_FILTER_IGNORE
    layer.add_child(ui)
    sas_hud=SasHUD.new();sas_hud.scale=Vector2(.74,.74);ui.add_child(sas_hud)
    sas_hud.toggled.connect(toggle_sas)
    sas_hud.mode_selected.connect(select_sas_mode)
    var theme = Theme.new()
    theme.default_font_size=14
    var normal = StyleBoxFlat.new()
    normal.bg_color=Color(.055,.1,.16,.95)
    normal.border_color=Color(.21,.33,.47)
    normal.set_border_width_all(1)
    normal.set_corner_radius_all(5)
    normal.content_margin_left=12
    normal.content_margin_right=12
    normal.content_margin_top=8
    normal.content_margin_bottom=8
    theme.set_stylebox("normal","Button",normal)
    var hover=normal.duplicate()
    hover.bg_color=Color(.09,.2,.31)
    theme.set_stylebox("hover","Button",hover)
    theme.set_stylebox("pressed","Button",hover)
    theme.set_color("font_color","Button",Color(.82,.91,1))
    theme.set_color("font_color","Label",Color(.8,.87,.95))
    ui.theme=theme
    var header = panel(ui,Vector2(18,16),Vector2(1404,64))
    widgets.header=header
    var row = HBoxContainer.new()
    row.add_theme_constant_override("separation",22)
    header.add_child(row)
    row.add_child(label_text("/ /  A S T R A",22,Color(.86,.95,1)))
    row.add_child(label_text("DESKTOP  /  MISSION CONTROL",11,Color(.45,.65,.83)))
    var spacer = Control.new()
    spacer.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    row.add_child(spacer)
    widgets.status=label_text("CONNESSIONE AL MOTORE",11)
    row.add_child(widgets.status)
    button("GRAFICA",show_graphics,row)
    button("CONTROLLER",show_controller,row)
    var left = panel(ui,Vector2(18,96),Vector2(270,640))
    widgets.left=left
    var column=VBoxContainer.new()
    column.add_theme_constant_override("separation",10)
    var left_scroll=ScrollContainer.new()
    left_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
    left.add_child(left_scroll)
    left_scroll.add_child(column)
    column.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    column.add_child(label_text("OPERAZIONI DI VOLO",11,Color(.4,.65,.9)))
    mode_selection=OptionButton.new()
    mode_selection.add_item("SIMULATORE · missioni e analisi")
    mode_selection.add_item("GIOCA · carriera e missioni")
    column.add_child(mode_selection)
    mission_selection=OptionButton.new()
    mission_selection.fit_to_longest_item=false
    mission_selection.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
    mission_selection.custom_minimum_size.x=220
    column.add_child(mission_selection)
    mode_selection.item_selected.connect(change_product_mode)
    mission_selection.item_selected.connect(select_activity)
    widgets.game_status=label_text("SCEGLI UNA MISSIONE",11,Color(.55,.8,1))
    widgets.game_status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
    widgets.game_status.visible=false
    column.add_child(widgets.game_status)
    widgets.game_map=MissionMap.new();column.add_child(widgets.game_map);widgets.game_map.visible=false
    widgets.game_board=button("APRI BACHECA MISSIONI",show_game_missions_current,column)
    widgets.game_board.visible=false
    widgets.game_manual=button("ATTIVA CONTROLLO TASTIERA",manual_keyboard,column)
    widgets.game_manual.visible=false
    widgets.game_actions=VBoxContainer.new();column.add_child(widgets.game_actions)
    widgets.game_checkpoint=button(mission_text("checkpoint"),func():game_action("checkpoint",{"action":"save"}),widgets.game_actions)
    widgets.game_restore=button(mission_text("restore"),func():game_action("checkpoint",{"action":"restore"}),widgets.game_actions)
    widgets.game_retry=button(mission_text("retry"),func():game_action("retry"),widgets.game_actions)
    widgets.game_actions.visible=false
    widgets.sim_controls=[]
    var profile_label=label_text("PROFILO FISICO ASTRA",10);column.add_child(profile_label);widgets.sim_controls.append(profile_label)
    model_selection=OptionButton.new()
    model_selection.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
    column.add_child(model_selection);widgets.sim_controls.append(model_selection)
    model_selection.item_selected.connect(func(_i):reset_mission())
    advanced=CheckBox.new()
    advanced.text="13 modelli avanzati nel motore"
    advanced.button_pressed=true
    column.add_child(advanced);widgets.sim_controls.append(advanced)
    advanced.toggled.connect(func(_v):reset_mission())
    widgets.play=button("AVVIA MISSIONE",toggle_play,column)
    var step_button=button("PASSO FISICO  +0,1 s",step_once,column);widgets.sim_controls.append(step_button)
    var reset_button=button("RESET MISSIONE",reset_mission,column);widgets.sim_controls.append(reset_button)
    var speed=OptionButton.new()
    for text in ["1× · tempo reale","10× · accelerato","100× · rapido"]:speed.add_item(text)
    speed.item_selected.connect(func(i):request("/desktop/speed",{"speed":[1,10,100][i]}))
    column.add_child(speed);widgets.sim_controls.append(speed)
    widgets.automatic=button("GNC AUTOMATICO",automatic,column);widgets.sim_controls.append(widgets.automatic)
    var keyboard_button=button("CONTROLLO DA TASTIERA",manual_keyboard,column);widgets.sim_controls.append(keyboard_button)
    var sim_separator=HSeparator.new();column.add_child(sim_separator);widgets.sim_controls.append(sim_separator)
    for entry in [["LABORATORI DI INGEGNERIA",show_laboratory],["VEHICLE LAB / STADI",show_vehicle_lab],
        ["DATI / REPLAY / VERIFICHE",show_data_lab],["SISTEMA SOLARE / TRANSFER",show_celestial],
        ["API PYTHON / AUTOMAZIONE",show_python],["ASSET 3D / IMPORTA GLB",show_assets]]:
        widgets.sim_controls.append(button(entry[0],entry[1],column))
    widgets.career_button=button("CARRIERA · CREDITI / SCIENZA",show_career,column)
    change_product_mode(0)
    var right=panel(ui,Vector2(1080,96),Vector2(342,640))
    widgets.right=right
    var tabs=TabContainer.new()
    tabs.size_flags_vertical=Control.SIZE_EXPAND_FILL
    right.add_child(tabs)
    var telemetry=VBoxContainer.new()
    var telemetry_scroll=ScrollContainer.new()
    telemetry_scroll.name="VOLO"
    telemetry_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
    tabs.add_child(telemetry_scroll)
    telemetry_scroll.add_child(telemetry)
    telemetry.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    telemetry.add_child(label_text("SOLUZIONE DI NAVIGAZIONE",10,Color(.4,.65,.9)))
    widgets.phase=label_text("READY",18,Color(.85,.95,1))
    telemetry.add_child(widgets.phase)
    for pair in [["altitude","QUOTA","m"],["speed","VELOCITÀ","m/s"],["resource","RISORSA","%"],["load","CARICO","g"],["qbar","PRESSIONE DINAMICA","Pa"]]:
        telemetry.add_child(label_text(pair[1],10,Color(.4,.57,.72)))
        var value=label_text("— "+pair[2],26,Color(.9,.96,1))
        telemetry.add_child(value)
        widgets[pair[0]]=value
    widgets.attitude=label_text("ASSETTO  —",12)
    telemetry.add_child(widgets.attitude)
    widgets.clock_owner=label_text("CLOCK · DESKTOP",11,Color(.5,.75,.95))
    telemetry.add_child(widgets.clock_owner)
    widgets.render=label_text("RENDERER",10)
    telemetry.add_child(widgets.render)
    telemetry.add_child(HSeparator.new())
    telemetry.add_child(label_text("DATI ESSENZIALI · DETTAGLI",10,Color(.4,.65,.9)))
    for entry in [["attitude","ASSETTO E ROTAZIONE"],["position","POSIZIONE E VELOCITÀ"],["orbit","ORBITA E RENDEZVOUS"],["flight","MECCANICA DEL VOLO"],["propulsion","PROPULSIONE ED ENERGIA"],["navigation","NAVIGAZIONE E COMANDI"]]:
        var container=VBoxContainer.new()
        telemetry.add_child(container)
        var toggle=Button.new();toggle.text="▸  "+entry[1];toggle.toggle_mode=true
        toggle.alignment=HORIZONTAL_ALIGNMENT_LEFT;toggle.add_theme_font_size_override("font_size",11)
        toggle.custom_minimum_size.y=34;container.add_child(toggle)
        var content=VBoxContainer.new();content.visible=false;container.add_child(content)
        detail_widgets[entry[0]]={"toggle":toggle,"content":content,"values":[],"note":null}
        toggle.toggled.connect(func(open):
            content.visible=open;toggle.text=("▾  " if open else "▸  ")+entry[1]
            update_flight_details(true))
    var sciences=VBoxContainer.new()
    sciences.name="MODELLI"
    tabs.add_child(sciences)
    sciences.add_child(label_text("13 DISCIPLINE · STATO / LIMITI",10,Color(.4,.65,.9)))
    var tree=Tree.new()
    tree.columns=2
    tree.hide_root=true
    tree.size_flags_vertical=Control.SIZE_EXPAND_FILL
    sciences.add_child(tree)
    widgets.science=tree
    var manual=VBoxContainer.new()
    var manual_scroll=ScrollContainer.new();manual_scroll.name="GNC"
    tabs.add_child(manual_scroll);manual_scroll.add_child(manual)
    manual.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    manual.add_child(label_text("COMANDI MANUALI",11))
    manual.add_child(label_text("SAS · ASSETTO ORBITALE",10,Color(.4,.65,.9)))
    sas_selection=OptionButton.new()
    var sas_modes=[["Manuale · inerziale","manual"],["Stability Assist","stability_assist"],
        ["Prograde","prograde"],["Retrograde","retrograde"],
        ["Radiale entrante","radial_in"],["Radiale uscente","radial_out"],
        ["Normale orbitale","normal"],["Anti-normale orbitale","anti_normal"],
        ["Punta al target","target"],["Anti-target","anti_target"],["Nodo di manovra","maneuver_node"]]
    for entry in sas_modes:
        sas_selection.add_item(entry[0]);sas_selection.set_item_metadata(sas_selection.item_count-1,entry[1])
    manual.add_child(sas_selection)
    sas_selection.item_selected.connect(func(index):
        select_sas_mode(str(sas_selection.get_item_metadata(index))))
    widgets.manual_axes={}
    for axis in [["throttle_pct","SPINTA",0,100,0],["roll_deg","ROLL",-60,60,0],["pitch_deg","PITCH",-45,90,0],["yaw_deg","YAW",-180,180,0],["brakes_pct","FRENI",0,100,0]]:
        manual.add_child(label_text(axis[1],10))
        var slider=HSlider.new()
        slider.min_value=axis[2];slider.max_value=axis[3];slider.value=axis[4]
        slider.value_changed.connect(func(value):manual_axis(axis[0],value))
        manual.add_child(slider)
        widgets.manual_axes[axis[0]]=slider
    widgets.input_status=label_text("COMANDI DISARMATI",11,Color(.6,.75,.9))
    manual.add_child(widgets.input_status)
    manual.add_child(label_text("SPAZIO avvio/pausa · M manuale\nG automatico · WASD assetto\nT SAS · Z/X preset precedente/successivo\nQ/E imbardata · Shift/Ctrl spinta\nTasto destro: camera · Rotella: zoom",12))
    var bottom=panel(ui,Vector2(306,760),Vector2(756,120))
    widgets.bottom=bottom
    var details=VBoxContainer.new()
    bottom.add_child(details)
    widgets.vehicle=label_text("ASTRA · MOTORE SCIENTIFICO SI",15,Color(.88,.94,1))
    details.add_child(widgets.vehicle)
    widgets.time=label_text("T + 00:00:00",24)
    details.add_child(widgets.time)
    widgets.note=label_text("Finestra desktop nativa · fisica Python · nessun browser richiesto",11)
    details.add_child(widgets.note)
    get_viewport().size_changed.connect(resize_ui)
    resize_ui()

func resize_ui():
    var size=get_viewport().get_visible_rect().size
    widgets.header.size.x=size.x-36
    widgets.left.size.y=size.y-194
    widgets.right.position.x=size.x-360
    widgets.right.size.y=size.y-194
    widgets.bottom.position.y=size.y-112
    widgets.bottom.size=Vector2(maxf(300,size.x-684),96)
    sas_hud.position=Vector2(306,maxf(92,size.y-354))

func fill_models():
    model_selection.clear()
    if scenario=="planetary":
        model_selection.add_item("ASTRA Lunar Lander · 1000 kg")
        return
    if scenario=="orbital":
        model_selection.add_item("ASTRA LEO Servicer")
        model_selection.set_item_metadata(0,"astra-leo-servicer")
        return
    var options=models.get(vehicle,{})
    for key in options:
        if key=="astra-leo-servicer":continue
        model_selection.add_item(str(options[key].get("name",key)))
        model_selection.set_item_metadata(model_selection.item_count-1,key)
    if vehicle=="space" and custom_design!=null:
        model_selection.add_item(str(custom_design.name))
        model_selection.set_item_metadata(model_selection.item_count-1,"astra-custom-stack")

func change_product_mode(index):
    game_mode=index==1
    mission_selection.clear()
    if game_mode:
        for entry in [["GIOCA · SPAZIO","space"],["GIOCA · AEREO","aircraft"],["GIOCA · DRONE","drone"]]:
            mission_selection.add_item(entry[0]);mission_selection.set_item_metadata(mission_selection.item_count-1,entry[1])
        var category="space" if vehicle=="space" else "aircraft" if vehicle=="aircraft" else "drone"
        for i in range(mission_selection.item_count):
            if mission_selection.get_item_metadata(i)==category:mission_selection.select(i);break
    else:
        for text in ["SPAZIO · lancio e recupero","SPAZIO · rendezvous LEO","LUNA · discesa 6-DoF",
            "AEREO · decollo e circuito","UAV · ispezione e rientro","SPAZIO · LEO completo"]:
            mission_selection.add_item(text)
        var selected=3 if vehicle=="aircraft" else 4 if vehicle=="drone" else 1 if scenario=="orbital" else 2 if scenario=="planetary" else 5 if scenario=="leo-return" else 0
        mission_selection.select(selected)
    for control in widgets.get("sim_controls",[]):control.visible=not game_mode
    widgets.game_status.visible=game_mode
    widgets.game_board.visible=game_mode
    widgets.game_manual.visible=game_mode and free_mode
    if not game_mode:widgets.game_map.visible=false
    widgets.play.visible=not game_mode or free_mode
    if not game_mode:
        widgets.game_status.text=""

func select_activity(index):
    if game_mode:
        show_game_missions(str(mission_selection.get_item_metadata(index)))
        return
    change_mission(index)

func change_mission(index):
    pilot.disarm();keyboard_active=false
    free_mode=index>=6
    vehicle=["space","space","space","aircraft","drone","space","space","space","aircraft","drone","space"][index]
    scenario=["mission","orbital","planetary","mission","mission","leo-return","mission","orbital","mission","mission","planetary"][index]
    pilot.load_profile(vehicle)
    fill_models()
    scene.asset_choice="auto";scene.selected_asset=""
    scene.catalogue_asset={}
    if scenario=="leo-return" and custom_design==null:
        show_vehicle_lab()
        return
    reset_mission()

func reset_mission():
    pilot.disarm();keyboard_active=false;replay_index=-1;awarded=false
    if model_selection==null or model_selection.item_count==0:return
    var payload={"vehicle":vehicle,"scenario":scenario,"advanced_models":advanced.button_pressed}
    var model=model_selection.get_item_metadata(model_selection.selected)
    if model!=null:payload.model_id=model
    if scenario=="leo-return" or model=="astra-custom-stack":
        payload.model_id="astra-custom-stack"
        payload.custom_design=custom_design
    reset_pending=true
    var reply=await request("/desktop/free" if free_mode else "/reset",payload)
    reset_pending=false
    report_result(reply)
    await poll()

func poll():
    if pending:return
    pending=true
    var snapshot=await request("/desktop/snapshot")
    pending=false
    if snapshot.has("error"):
        widgets.status.text=str(snapshot.error)
        return
    state=snapshot.state
    desktop=snapshot.desktop
    details=snapshot.get("flight_details",[])
    free_mode=desktop.get("play_mode","mission")=="free"
    game_state=snapshot.get("game",{})
    game_career=snapshot.get("career",{})
    if not game_language_loaded:
        game_language=str(game_career.get("preferences",{}).get("language","it"))
        game_language_loaded=true
    var view_changed=int(snapshot.get("view",{}).get("revision",-1))!=view_revision
    if view_changed:
        view_revision=int(snapshot.view.revision);view_settings=snapshot.view.settings
        view_changed_keys=snapshot.view.get("changed",view_settings.keys())
        if "model" in snapshot.view.get("changed",[]):scene.asset_choice=str(view_settings.model);scene.model_key=""
    if not reset_pending and int(desktop.get("revision",0))!=seen_revision:
        seen_revision=int(desktop.get("revision",0))
        sync_mission_controls()
    if replay_index<0:scene.set_snapshot(snapshot)
    if view_changed:apply_view()
    if not capture_busy:
        for job in snapshot.get("capture_requests",[]):
            if not captures_seen.has(job.id):
                captures_seen[job.id]=true;capture_busy=true;capture_frame.call_deferred(job);break
    update_hud()

func apply_view():
    if "quality" in view_changed_keys:
        scene.set_quality(str(view_settings.quality))
        quality="MEDIO" if view_settings.quality=="balanced" else str(view_settings.quality).to_upper()
    if "enhanced_materials" in view_changed_keys:
        scene.enhanced_materials=bool(view_settings.enhanced_materials)
        if not scene.physical_state.is_empty():scene.build_vehicle()
    if "earthshine" in view_changed_keys:
        scene.earthshine=bool(view_settings.earthshine)
        scene.earthshine_light.light_energy=.12 if scene.earthshine and scene.quality!="low" else 0.0
    if "cinematic_effects" in view_changed_keys:scene.cinematic_effects=bool(view_settings.cinematic_effects)
    if "audio_enabled" in view_changed_keys:scene.effects.audio_enabled=bool(view_settings.audio_enabled)
    if "audio_volume" in view_changed_keys:scene.effects.audio_volume=float(view_settings.audio_volume)
    if "azimuth_deg" in view_changed_keys:scene.azimuth=deg_to_rad(float(view_settings.azimuth_deg))
    if "elevation_deg" in view_changed_keys:scene.elevation=deg_to_rad(float(view_settings.elevation_deg))
    if "distance_m" in view_changed_keys and view_settings.distance_m!=null:scene.distance=float(view_settings.distance_m)
    if "exposure" in view_changed_keys:scene.environment.tonemap_exposure=float(view_settings.exposure)
    if "nebula_strength" in view_changed_keys:scene.sky_material.set_shader_parameter("nebula_strength",float(view_settings.nebula_strength))
    if "resolution_scale" in view_changed_keys:
        var scale=float(view_settings.resolution_scale)
        get_viewport().scaling_3d_mode=Viewport.SCALING_3D_MODE_FSR2 if scene.advanced_renderer and scene.quality=="balanced" and scale<=1.0 else Viewport.SCALING_3D_MODE_BILINEAR
        get_viewport().scaling_3d_scale=scale
    if "show_ui" in view_changed_keys:ui.visible=bool(view_settings.show_ui)
    if "auto_exposure" in view_changed_keys:scene.camera.attributes.auto_exposure_enabled=bool(view_settings.auto_exposure) and scene.advanced_renderer
    if "depth_of_field" in view_changed_keys:
        scene.camera.attributes.dof_blur_far_enabled=bool(view_settings.depth_of_field) and scene.advanced_renderer
        scene.camera.attributes.dof_blur_near_enabled=bool(view_settings.depth_of_field) and scene.advanced_renderer

func capture_frame(job):
    ui.visible=bool(job.include_ui)
    await get_tree().process_frame
    await RenderingServer.frame_post_draw
    var frame=get_viewport().get_texture().get_image()
    var error=""
    if frame==null:error="Frame GPU non disponibile"
    elif frame.save_png(str(job.path))!=OK:error="Impossibile salvare il PNG"
    ui.visible=bool(view_settings.get("show_ui",true))
    await request("/desktop/capture/complete",{"id":job.id,"error":error,"width":frame.get_width() if frame!=null else 0,"height":frame.get_height() if frame!=null else 0})
    capture_busy=false
    if captures_seen.size()>64:captures_seen.clear()

func render_report():
    render_pending=true
    await request("/desktop/render",{"backend":RenderingServer.get_current_rendering_method(),"adapter":RenderingServer.get_video_adapter_name(),
        "fps":Engine.get_frames_per_second(),"frame_time_ms":frame_times[-1] if not frame_times.is_empty() else 0,"draw_calls":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
        "primitives":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
        "objects":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
        "asset_id":scene.active_asset_id,"asset_file":scene.selected_asset.get_file(),"asset_loaded":scene.last_model_import_ok,"asset_error":scene.asset_error,
        "cache_loads":scene.assets.loads,"cache_hits":scene.assets.cache_hits,"view_revision":view_revision,"resolution_scale":get_viewport().scaling_3d_scale,
        "input_revision":"2.4.1","input_rtt_ms":pilot_rtt_ms,
        "camera":{"azimuth_deg":rad_to_deg(scene.azimuth),"elevation_deg":rad_to_deg(scene.elevation),"distance_m":scene.distance}})
    render_pending=false

func sync_mission_controls():
    # Python and environment resets must select the same mission in the GUI.
    var new_vehicle=str(state.get("vehicle","space"))
    var new_scenario=str(state.get("scenario","mission"))
    if new_vehicle!=vehicle or new_scenario!=scenario:
        pilot.disarm();keyboard_active=false
        vehicle=new_vehicle;scenario=new_scenario
        pilot.load_profile(vehicle)
        fill_models()
    if game_state.get("active",false) and not game_mode:
        mode_selection.select(1);change_product_mode(1)
    elif not free_mode and game_mode and not game_state.get("active",false):
        mode_selection.select(0);change_product_mode(0)
    var index=3 if vehicle=="aircraft" else 4 if vehicle=="drone" else 1 if scenario=="orbital" else 2 if scenario=="planetary" else 5 if scenario=="leo-return" else 0
    if game_mode:
        index=0 if vehicle=="space" else 1 if vehicle=="aircraft" else 2
    mission_selection.select(index)
    for i in range(model_selection.item_count):
        if model_selection.get_item_metadata(i)==state.get("model_id"):
            model_selection.select(i)
    advanced.set_pressed_no_signal(bool(state.get("science",{}).get("enabled",true)))
    for key in widgets.manual_axes:
        if state.get("command",{}).get(key)!=null:widgets.manual_axes[key].set_value_no_signal(float(state.command[key]))
    if sas_selection!=null:
        sync_sas()

func sync_sas():
    if sas_selection!=null:
        var sas=state.get("sas",{})
        var current_sas=str(sas.get("mode","manual")) if sas.get("enabled",false) else "manual"
        var expected=["manual"]
        for entry in SasHUD.MODES:expected.append(entry[0])
        var existing=[]
        for i in range(sas_selection.item_count):existing.append(str(sas_selection.get_item_metadata(i)))
        if existing!=expected:
            sas_selection.clear()
            for key in expected:
                var caption="Manuale · inerziale"
                for entry in SasHUD.MODES:
                    if entry[0]==key:caption=entry[2]
                sas_selection.add_item(caption);sas_selection.set_item_metadata(sas_selection.item_count-1,key)
        for i in range(sas_selection.item_count):
            var mode_key=str(sas_selection.get_item_metadata(i))
            sas_selection.set_item_disabled(i,mode_key!="manual" and mode_key not in sas.get("available_modes",[]))
            if str(sas_selection.get_item_metadata(i))==current_sas:
                sas_selection.select(i)
        sas_hud.update_state(sas)

func update_hud():
    sync_sas()
    widgets.status.text="●  MOTORE COLLEGATO  /  API v1"
    widgets.phase.text=str(state.get("phase","READY")).replace("_"," ")
    if free_mode and vehicle=="space" and scenario=="mission" and not state.get("mission_started",false):widgets.phase.text="READY · ATTESA SPINTA"
    widgets.altitude.text=format_number(state.get("altitude_m",0))+" m"
    widgets.speed.text=format_number(state.get("air_relative_speed_m_s",state.get("speed_m_s",0)))+" m/s"
    var battery=state.get("battery",{})
    var resource=state.get("battery_pct",state.get("propellant_pct",battery.get("state_of_charge_pct",100)))
    widgets.resource.text=format_number(resource)+" %"
    widgets.load.text=format_number(state.get("load_factor_g",0))+" g"
    widgets.qbar.text=format_number(state.get("environment",{}).get("dynamic_pressure_Pa",0))+" Pa"
    widgets.vehicle.text=str(state.get("vehicle_name",state.get("model_id","ASTRA")))+"  /  "+str(state.get("frame","SI"))
    var seconds=int(state.get("time_s",0))
    widgets.time.text="T + %02d:%02d:%02d"%[seconds/3600,(seconds/60)%60,seconds%60]
    var att=state.get("attitude_deg",[0,0,0])
    if att!=null:widgets.attitude.text="R/P/Y  %.1f°  %.1f°  %.1f°"%[float(att[0]),float(att[1]),float(att[2])]
    widgets.clock_owner.text="CLOCK · "+str(desktop.get("clock_owner","desktop")).to_upper()
    widgets.play.text="PAUSA" if desktop.get("running",false) else "GIOCA / RIPRENDI" if free_mode else "RIPRENDI" if state.get("mission_started",false) else "AVVIA MISSIONE"
    widgets.automatic.text="PAUSA SICURA" if free_mode else "GNC AUTOMATICO"
    widgets.input_status.text="TASTIERA ATTIVA" if keyboard_active else "CONTROLLER ARMATO" if pilot.armed else "CONTROLLO PYTHON" if state.get("command",{}).get("mode")=="python" else "RIFERIMENTI MANUALI" if state.get("command",{}).get("mode")=="manual" else "GNC AUTOMATICO"
    widgets.render.text="%s · %d FPS · %.1f ms · %s"%[RenderingServer.get_current_rendering_method().to_upper(),Engine.get_frames_per_second(),frame_times[-1] if not frame_times.is_empty() else 0.0,quality.to_upper()]
    widgets.note.text=scene.asset_error if scene.asset_error!="" else "VISIVO: "+str(scene.active_asset.get("name",""))+" · F2 vista 3D"
    widgets.note.tooltip_text=str(scene.active_asset.get("source",""))+"\n"+str(scene.active_asset.get("license",""))+"\n"+str(scene.active_asset.get("source_url",""))
    widgets.play.visible=not game_mode or free_mode
    widgets.game_board.visible=game_mode
    widgets.game_manual.visible=game_mode and free_mode
    widgets.game_actions.visible=game_mode and game_state.get("active",false)
    widgets.game_map.set_flight(game_state.get("mission",{}) if game_state.get("active",false) else {},state,game_state)
    widgets.game_map.visible=widgets.game_map.visible and game_mode
    widgets.game_restore.disabled=not game_state.get("checkpoint_available",false)
    widgets.game_checkpoint.text=mission_text("checkpoint")
    widgets.game_restore.text=mission_text("restore")
    widgets.game_retry.text=mission_text("retry")
    sas_selection.visible=true
    if game_mode:
        if game_state.get("active",false):
            var active_mission=game_state.mission
            var lines=[str(active_mission.campaign),str(active_mission.title),"T+ %s s  ·  tratta %s m"%[
                format_number(game_state.get("elapsed_s",0)),format_number(game_state.get("distance_m",0))]]
            if not game_state.get("objective_progress",[]).is_empty():
                for objective in game_state.objective_progress:
                    lines.append(("✓  " if objective.get("complete",false) else "○  ")+str(objective.label)+"  %d%%"%roundi(float(objective.get("fraction",0))*100))
            else:
                for objective in active_mission.objectives:
                    var done=bool(game_state.get("progress",{}).get(objective.type,false))
                    lines.append(("✓  " if done else "○  ")+str(objective.label))
            lines.append(mission_text("controls"))
            var nav=game_state.get("navigation",{})
            if not nav.is_empty():
                lines.append("WP %s/%s · %s m · %s m/s"%[str(nav.get("index",0)),str(nav.get("total",0)),format_number(nav.get("distance_m",0)),format_number(nav.get("speed_m_s",0))])
            if game_state.get("hint","")!="":lines.append(mission_text("hint")+": "+str(game_state.hint))
            widgets.game_status.text="\n".join(lines)
            if (game_state.get("complete",false) or game_state.get("failed",false)) and game_result_seen!=str(active_mission.id):
                game_result_seen=str(active_mission.id)
                show_game_result.call_deferred()
        else:
            widgets.game_status.text="SCEGLI UNA DELLE TRE DISCIPLINE, POI APRI LA BACHECA MISSIONI"
    var tree=widgets.science
    if tree.is_visible_in_tree() and Time.get_ticks_msec()-last_science_update_ms>350:
        last_science_update_ms=Time.get_ticks_msec()
        var expanded=[]
        var old_root=tree.get_root()
        if old_root!=null:
            var item=old_root.get_first_child()
            while item!=null:
                if not item.collapsed:expanded.append(item.get_text(0))
                item=item.get_next()
        tree.clear()
        var root=tree.create_item()
        for key in state.get("science",{}).get("disciplines",{}):
            var model=state.science.disciplines[key]
            var row=tree.create_item(root)
            row.set_text(0,key.replace("-"," ").to_upper())
            row.set_text(1,"ATTIVO" if model.status=="ACTIVE" else "N/A")
            row.set_tooltip_text(0,str(model.limits)+"\n"+str(model.coupling))
            row.collapsed=row.get_text(0) not in expanded
            for value in model.get("values",{}):
                var child=tree.create_item(row)
                child.set_text(0,str(value))
                var content=model.values[value]
                child.set_text(1,format_number(content) if content is float or content is int else str(content).left(90))
                child.set_tooltip_text(1,str(content))
    var terminal=state.get("phase","") in ["LANDED","CRASHED","ABORTED"]
    update_flight_details()
    if terminal and not awarded and not free_mode:
        awarded=true
        career.xp+=200 if state.phase=="LANDED" else 30
        career.missions+=1
        save_career()

func detail_number(value):
    if value==null:return "—"
    if value is bool:return "SÌ" if value else "NO"
    if value is int or value is float:
        var number=float(value)
        if absf(number)>=1e8 or (absf(number)>0 and absf(number)<.0001):return "%.5e"%number
        return ("%.4f"%number).trim_suffix("000").trim_suffix("00").trim_suffix("0").trim_suffix(".")
    return str(value)

func update_flight_details(force=false):
    if not force and Time.get_ticks_msec()-last_detail_update<400:return
    last_detail_update=Time.get_ticks_msec()
    for section in details:
        if not detail_widgets.has(section.id):continue
        var entry=detail_widgets[section.id]
        if not entry.content.visible:continue
        if entry.values.size()!=section.rows.size():
            for child in entry.content.get_children():entry.content.remove_child(child);child.queue_free()
            entry.values.clear()
            entry.note=label_text(section.get("note",""),10,Color(.48,.66,.8))
            entry.note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;entry.content.add_child(entry.note)
            for item in section.rows:
                var row=HBoxContainer.new();entry.content.add_child(row)
                var title=label_text(item.label,11,Color(.57,.72,.85))
                title.custom_minimum_size.x=140;title.size_flags_horizontal=Control.SIZE_EXPAND_FILL
                title.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;row.add_child(title)
                var value=label_text("",12,Color(.88,.95,1));value.custom_minimum_size.x=102
                value.size_flags_horizontal=Control.SIZE_EXPAND_FILL;value.horizontal_alignment=HORIZONTAL_ALIGNMENT_RIGHT
                value.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;row.add_child(value)
                entry.values.append({"title":title,"value":value})
        entry.note.text=section.get("note","")
        for i in range(section.rows.size()):
            var item=section.rows[i]
            entry.values[i].title.text=item.label
            entry.values[i].value.text=detail_number(item.value)+(" "+item.unit if item.unit!="" and item.value!=null else "")
            entry.values[i].value.tooltip_text=item.label+": "+str(item.value)+" "+item.unit

func format_number(value):
    if not (value is float or value is int):return "—"
    if absf(float(value))>999999:return str(float(value))
    return "%.1f"%float(value)

func toggle_play():
    replay_index=-1
    await request("/desktop/pause" if desktop.get("running",false) else "/desktop/play",{})
    await poll()

func step_once():
    await request("/step",{"dt_s":.1})
    await poll()

func automatic():
    keyboard_active=false;pilot.disarm()
    latest_pilot_command={};pilot_error=""
    await request("/desktop/pilot",{"armed":false})
    await request("/command",{"mode":"auto"})
    await poll()

func manual_keyboard():
    pilot.disarm();keyboard_active=true
    keyboard_throttle=float(state.get("command",{}).get("throttle_pct",0))
    var target=state.get("attitude_target_deg",[0,0,0])
    keyboard_target=Vector3(float(target[0]),float(target[1]),float(target[2]))
    if scenario=="orbital":
        var manual_command={"mode":"manual","attitude_torque_body_fraction":[0,0,0]}
        if not state.get("sas",{}).get("enabled",false):manual_command.attitude_sas_mode="manual"
        request("/command",manual_command)
    else:request("/command",{"mode":"manual"})
    widgets.note.text="MANUALE · WASD / Q E · Shift/Ctrl spinta · G riprende il GNC"

func manual_axis(key,value):
    keyboard_active=false;pilot.disarm()
    var command={key:value,"mode":"manual"}
    if scenario=="orbital" and key in ["roll_deg","pitch_deg","yaw_deg"]:
        var fractions=state.get("command",{}).get("attitude_torque_body_fraction",[0,0,0]).duplicate()
        var axis=["roll_deg","pitch_deg","yaw_deg"].find(key)
        fractions[axis]=clampf(value/[60.0,45.0,180.0][axis],-1.0,1.0)
        command.attitude_torque_body_fraction=fractions
        command.attitude_sas_mode=str(sas_selection.get_item_metadata(sas_selection.selected))
    request("/command",command)

func toggle_sas():
    if not state.get("sas",{}).get("supported",false) or sas_request_pending:return
    sas_request_pending=true
    var reply=await request("/command",{"mode":"manual","sas_enabled":not state.sas.get("enabled",false)})
    report_result(reply)
    if not reply.has("error"):
        state=reply
        enable_sas_pilot_input()
    sas_request_pending=false
    await poll()

func select_sas_mode(mode):
    if sas_request_pending or not state.get("sas",{}).get("supported",false):return
    if mode!="manual" and mode not in state.sas.get("available_modes",[]):return
    sas_request_pending=true
    var reply=await request("/command",{"mode":"manual","attitude_sas_mode":mode})
    report_result(reply)
    if not reply.has("error"):
        state=reply
        enable_sas_pilot_input()
    sas_request_pending=false
    await poll()

func cycle_sas(direction=1):
    var modes=state.get("sas",{}).get("available_modes",[])
    if modes.is_empty():return
    var current=modes.find(state.sas.get("mode","stability_assist"))
    if current<0:current=0 if direction<0 else -1
    select_sas_mode(modes[posmod(current+direction,modes.size())])

func enable_sas_pilot_input():
    if not pilot.armed and desktop.get("clock_owner","desktop")=="desktop":
        keyboard_throttle=float(state.get("command",{}).get("throttle_pct",0))
        keyboard_active=true

func _process(dt):
    if validation_mode:return
    if python_proof_path!="" and not python_proof_started and FileAccess.file_exists(python_proof_data) and state.get("command",{}).get("mode")=="python":
        python_proof_started=true;capture_python_proof.call_deferred()
    renderer_frames+=1
    frame_times.append(dt*1000)
    if frame_times.size()>600:frame_times.pop_front()
    elapsed+=dt
    render_elapsed+=dt
    if render_elapsed>1.0 and not render_pending:
        render_elapsed=0.0;render_report()
    pilot_elapsed+=dt
    var snapshot_period=1.0/60.0 if pilot.armed or keyboard_active else 1.0/30.0
    if elapsed>=snapshot_period:
        elapsed=fmod(elapsed,snapshot_period)
        poll()
    latest_pilot_command=collect_pilot(minf(dt,.1))
    if pilot_elapsed>=PILOT_SEND_PERIOD and not pilot_pending and not latest_pilot_command.is_empty():
        pilot_elapsed=0.0
        send_pilot()
    pilot.capture_calibration()
    if smoke_path!="" and Time.get_ticks_msec()-start_wall>12000 and renderer_frames>120 and not state.is_empty():
        var destination=smoke_path
        smoke_path=""
        smoke_capture(destination)

func collect_pilot(dt):
    if desktop.get("clock_owner","desktop")=="external":
        pilot.disarm();keyboard_active=false
        return {}
    var command={}
    var focused=get_viewport().gui_get_focus_owner()
    var typing=focused is LineEdit or focused is TextEdit or focused is SpinBox
    if keyboard_active and typing:
        automatic()
        return {}
    if keyboard_active and not typing:
        keyboard_throttle=clampf(keyboard_throttle+(float(Input.is_key_pressed(KEY_SHIFT))-float(Input.is_key_pressed(KEY_CTRL)))*dt*float(pilot.config.throttle_rate_pct_s),0,100)
        command={"throttle_pct":keyboard_throttle,"roll_deg":(float(Input.is_key_pressed(KEY_D))-float(Input.is_key_pressed(KEY_A)))*30,
            "pitch_deg":(float(Input.is_key_pressed(KEY_S))-float(Input.is_key_pressed(KEY_W)))*20,
            "yaw_deg":(float(Input.is_key_pressed(KEY_E))-float(Input.is_key_pressed(KEY_Q)))*35,
            "brakes_pct":100 if Input.is_key_pressed(KEY_B) else 0}
        if vehicle=="space" and scenario not in ["orbital","planetary"]:
            command.pitch_deg=clampf(90.0+float(command.pitch_deg)*2.25,-45,90)
        if scenario=="orbital":
            command.attitude_torque_body_fraction=[
                clampf(float(command.roll_deg)/30.0,-1.0,1.0),
                clampf(-float(command.pitch_deg)/20.0,-1.0,1.0),
                clampf(float(command.yaw_deg)/35.0,-1.0,1.0)]
    elif pilot.armed:
        command=pilot.sample(dt,state)
        if command.has("disconnected"):
            automatic()
            return {}
    if not command.is_empty() and scenario!="orbital":
        command.sas_manual_input=pilot.smooth_axes.length()>.01 if pilot.armed else (Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_Q) or Input.is_key_pressed(KEY_E))
    return command

func send_pilot():
    var command=latest_pilot_command
    latest_pilot_command={}
    if command.is_empty():return
    pilot_pending=true
    var started=Time.get_ticks_usec()
    var reply=await request("/desktop/pilot",{"armed":true,"neutral_acquired":true,"compact":true,"command":command})
    pilot_rtt_ms=float(Time.get_ticks_usec()-started)*.001
    if reply.has("error"):
        pilot.disarm();keyboard_active=false
        pilot_error=str(reply.error)
    else:pilot_error=""
    pilot_pending=false

func configure_controller_ui():
    # Godot's built-in UI directions also bind the analog sticks. Remove
    # those bindings globally, including child Window/FileDialog viewports.
    # Polling Input.get_joy_axis() for flight remains fully active.
    for action in InputMap.get_actions():
        if not str(action).begins_with("ui_"):continue
        for binding in InputMap.action_get_events(action):
            if binding is InputEventJoypadMotion:InputMap.action_erase_event(action,binding)
    for pair in [["ui_up",JOY_BUTTON_DPAD_UP],["ui_down",JOY_BUTTON_DPAD_DOWN],
            ["ui_left",JOY_BUTTON_DPAD_LEFT],["ui_right",JOY_BUTTON_DPAD_RIGHT],
            ["ui_accept",JOY_BUTTON_A],["ui_cancel",JOY_BUTTON_B]]:
        for binding in InputMap.action_get_events(pair[0]):
            if binding is InputEventJoypadButton:InputMap.action_erase_event(pair[0],binding)
        var binding=InputEventJoypadButton.new()
        binding.device=-1;binding.button_index=pair[1]
        InputMap.action_add_event(pair[0],binding)

func route_hotas_menu_input(event):
    if event is InputEventJoypadButton and event.device==pilot.primary and pilot.config.input_kind=="hotas":
        _input(event)
        return true
    return false

func _input(event):
    if event is InputEventJoypadMotion:
        if controller_learn_axis!="" and event.device==pilot.primary and absf(event.axis_value-float(controller_learn_baseline[event.axis]))>.45:
            if is_instance_valid(controller_learn_editor):controller_learn_editor.value=event.axis
            controller_learn_axis=""
        get_viewport().set_input_as_handled()
        return
    if event is not InputEventJoypadButton or event.device!=pilot.primary:return
    if pilot.config.input_kind=="hotas":
        # Raw HOTAS button numbers must never invoke Xbox A/B/X/Y menu actions.
        get_viewport().set_input_as_handled()
        if not event.pressed:return
        var binding=int(event.button_index)
        if binding==int(pilot.config.arm_button):
            if pilot.armed:automatic()
            else:keyboard_active=false;pilot.arm(state)
        elif binding==int(pilot.config.pause_button):toggle_play()
        elif binding==int(pilot.config.gnc_button):automatic()
        elif binding==int(pilot.config.sas_toggle_button) and pilot.armed:toggle_sas()
        elif binding==int(pilot.config.sas_next_button) and pilot.armed:cycle_sas()
        return
    if event.button_index==int(pilot.config.sas_toggle_button) or event.button_index==int(pilot.config.sas_next_button):
        get_viewport().set_input_as_handled()
        if event.pressed and pilot.armed:
            if event.button_index==int(pilot.config.sas_toggle_button):toggle_sas()
            else:cycle_sas()
        return
    # D-pad navigates and A/B confirm/cancel via Godot's normal GUI actions.
    # Start is exclusively play/pause, so a focused GUI button cannot also
    # activate when the pilot resumes flight.
    if event.button_index not in [JOY_BUTTON_START,JOY_BUTTON_X,JOY_BUTTON_Y]:return
    get_viewport().set_input_as_handled()
    if not event.pressed:return
    match event.button_index:
        JOY_BUTTON_START:toggle_play()
        JOY_BUTTON_X:automatic()
        JOY_BUTTON_Y:
            if pilot.armed:automatic()
            else:pilot.arm(state)

func _unhandled_key_input(event):
    if event is not InputEventKey or not event.pressed or event.echo:return
    var focus=get_viewport().gui_get_focus_owner()
    if focus is LineEdit or focus is TextEdit:return
    match event.keycode:
        KEY_SPACE:toggle_play()
        KEY_G:automatic()
        KEY_M:manual_keyboard()
        KEY_T:toggle_sas()
        KEY_Z:cycle_sas(-1)
        KEY_X:cycle_sas(1)
        KEY_F11:DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED if DisplayServer.window_get_mode()==DisplayServer.WINDOW_MODE_FULLSCREEN else DisplayServer.WINDOW_MODE_FULLSCREEN)
        KEY_F2:request("/desktop/view",{"show_ui":not ui.visible})

func _notification(what):
    if what==NOTIFICATION_APPLICATION_FOCUS_OUT and is_instance_valid(ui) and (pilot.armed or keyboard_active):
        pilot.disarm();keyboard_active=false
        if desktop.get("clock_owner","desktop")!="external":automatic.call_deferred()

func joy_connection(_device,connected):
    if not connected and pilot.armed:automatic()

func report_result(value):
    if value is Dictionary and value.has("error"):widgets.note.text=str(value.error)
    elif is_instance_valid(result_view):result_view.text=JSON.stringify(value,"  ")

func window_panel(title,size=Vector2i(820,720)):
    var win=MenuWindow.new()
    win.title=title
    win.hotas_input_router=Callable(self,"route_hotas_menu_input")
    win.size=size
    win.min_size=Vector2i(620,460)
    win.close_requested.connect(win.queue_free)
    add_child(win)
    var margin=MarginContainer.new()
    margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    for edge in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+edge,18)
    win.add_child(margin)
    var scroll=ScrollContainer.new()
    margin.add_child(scroll)
    var box=VBoxContainer.new()
    box.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    box.add_theme_constant_override("separation",10)
    scroll.add_child(box)
    win.popup_centered()
    return box

func json_editor(parent,value,height=180):
    var edit=TextEdit.new()
    edit.text=JSON.stringify(value,"  ")
    edit.custom_minimum_size=Vector2(0,height)
    edit.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    parent.add_child(edit)
    return edit

func output_editor(parent,height=260):
    var edit=json_editor(parent,{},height)
    edit.editable=false
    return edit

func numeric(parent,text,value,low,high):
    var row=HBoxContainer.new()
    parent.add_child(row)
    var label=label_text(text,12)
    label.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    row.add_child(label)
    var edit=SpinBox.new()
    # Set precision before bounds/value: the default step of 1 otherwise
    # rounds 0.1 to 0 and 0.012 to 0.001 when merely opening this panel.
    edit.step=0.001 if absf(float(value))<10 else 0.1
    edit.min_value=low;edit.max_value=high;edit.value=value
    edit.allow_greater=false;edit.allow_lesser=false
    edit.custom_minimum_size.x=190
    row.add_child(edit)
    return edit

func save_dialog(default_name,content):
    var dialog=FileDialog.new()
    dialog.file_mode=FileDialog.FILE_MODE_SAVE_FILE
    dialog.access=FileDialog.ACCESS_FILESYSTEM
    dialog.current_file=default_name
    dialog.file_selected.connect(func(path):
        var file=FileAccess.open(path,FileAccess.WRITE)
        if file!=null:file.store_string(content)
        dialog.queue_free())
    dialog.canceled.connect(dialog.queue_free)
    add_child(dialog)
    dialog.popup_centered_ratio(.65)

func show_laboratory():
    var box=window_panel("ASTRA · Engineering Studio · 18 solutori SI")
    var selection=OptionButton.new()
    var keys=studies.keys()
    for key in keys:selection.add_item(studies[key].name)
    box.add_child(selection)
    var subtitle=label_text("",12)
    subtitle.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
    box.add_child(subtitle)
    var fields=VBoxContainer.new()
    box.add_child(fields)
    var editors={}
    var vectors={}
    var payload_extra=json_editor(box,{},75)
    var output=output_editor(box)
    var graph=load("res://plot.gd").new()
    graph.custom_minimum_size=Vector2(0,180)
    box.add_child(graph)
    var build_form=func(index):
        for c in fields.get_children():c.queue_free()
        editors.clear();vectors.clear()
        var study=studies[keys[index]]
        subtitle.text=study.get("subtitle","")
        for field in study.get("inputs",[]):editors[field[0]]=numeric(fields,field[1],field[2],field[3],field[4])
        for field in study.get("vectors",[]):
            fields.add_child(label_text(field[1],11))
            var axes=[]
            for i in range(field[2].size()):axes.append(numeric(fields,"  "+str(i),field[2][i],-1e12,1e12))
            vectors[field[0]]=axes
    selection.item_selected.connect(build_form)
    build_form.call(0)
    var solve=func(live):
        var data=JSON.parse_string(payload_extra.text)
        if not (data is Dictionary):output.text="Parametri aggiuntivi: oggetto JSON richiesto";return
        data.analysis=keys[selection.selected]
        for key in editors:
            data[key]=int(editors[key].value) if key in ["elements","spanwise_stations","seed","width_cells","height_cells","grid_width","grid_height","steps","stations","segments"] else editors[key].value
        for key in vectors:
            data[key]=[]
            for axis in vectors[key]:data[key].append(axis.value)
        output.text="Calcolo in corso…"
        var reply=await request("/engineering/live" if live else "/engineering",data)
        output.text=JSON.stringify(reply,"  ")
        var series=studies[keys[selection.selected]].get("series",[])
        if not series.is_empty():graph.set_samples(reply.get("samples",[]),series[0][0],series[0][1])
    button("CALCOLA STUDIO INDIPENDENTE",func():solve.call(false),box)
    button("STUDIO SUL CONTESTO DELLA MISSIONE",func():solve.call(true),box)
    button("ESPORTA RISULTATO JSON",func():save_dialog("astra-engineering.json",output.text),box)
    button("APPLICA ROTTA UAV ALLA MISSIONE PRONTA",func():
        var reply=await request("/mission/route",{"seed":42})
        output.text=JSON.stringify(reply,"  "),box)

func show_vehicle_lab():
    var box=window_panel("ASTRA · Vehicle Lab / Ambiente")
    box.add_child(label_text("Stack parametrico · i calcoli restano nel motore Python",13))
    var name=LineEdit.new();name.text="ASTRA Desktop LEO";box.add_child(name)
    var stages=numeric(box,"Numero stadi",3,1,6)
    var tanks=numeric(box,"Serbatoi per stadio",2,1,3)
    var engines=numeric(box,"Motori per stadio",1,1,8)
    var config=json_editor(box,{"name":"ASTRA Desktop LEO","stages":[{"tank_count":2,"engine_count":1},{"tank_count":2,"engine_count":1},{"tank_count":2,"engine_count":1}]})
    button("GENERA STACK",func():
        var list=[]
        for i in range(int(stages.value)):list.append({"tank_count":int(tanks.value),"engine_count":int(engines.value)})
        config.text=JSON.stringify({"name":name.text,"stages":list},"  "),box)
    button("APPLICA STACK / MISSIONE LEO",func():
        custom_design=JSON.parse_string(config.text)
        if not (custom_design is Dictionary):return
        vehicle="space";scenario="leo-return"
        mission_selection.select(5);fill_models()
        model_selection.select(model_selection.item_count-1)
        await reset_mission(),box)
    var wind=json_editor(box,{"vehicle":"aircraft","scenario":"mission","advanced_models":true,"wind_ned_m_s":[0,6,0]},130)
    button("APPLICA CONFIGURAZIONE AMBIENTE / RESET",func():
        var data=JSON.parse_string(wind.text)
        if data is Dictionary:
            var reply=await request("/reset",data)
            report_result(reply)
            await poll(),box)

func show_data_lab():
    var box=window_panel("ASTRA · Telemetria / Verifica / Replay",Vector2i(940,780))
    var selection=OptionButton.new()
    var endpoints=["/state","/desktop/recording","/fault","/fault/clear","/robustness","/convergence","/requirements/verify","/systems/configure"]
    for text in ["Telemetria completa","Registrazione missione","Iniezione guasto","Cancella guasti","Monte Carlo / robustezza","Convergenza numerica","Verifica requisiti","Configura sistemi di riferimento"]:selection.add_item(text)
    box.add_child(selection)
    var defaults=[{}, {}, {"type":"engine_thrust_loss","severity":0.3},{},{"vehicle":"drone","samples":4,"seed":42},{"vehicle":"drone","horizon_s":10},{"requirements":[{"id":"mass","field":"mass_kg","operator":">","value":0}]},{"panel_area_m2":4,"bus_load_W":180}]
    var body=json_editor(box,{},160)
    selection.item_selected.connect(func(i):body.text=JSON.stringify(defaults[i],"  "))
    var output=output_editor(box,310)
    var graph=load("res://plot.gd").new()
    graph.custom_minimum_size=Vector2(0,180)
    box.add_child(graph)
    button("ESEGUI",func():
        var endpoint=endpoints[selection.selected]
        var data=JSON.parse_string(body.text)
        if not (data is Dictionary):output.text="Oggetto JSON richiesto";return
        var reply=await request(endpoint,null if endpoint in ["/state","/desktop/recording"] else data)
        output.text=JSON.stringify(reply,"  "),box)
    button("GRAFICO QUOTA / MISSIONE",func():
        var data=await request("/desktop/recording")
        graph.set_samples(data.get("samples",[])),box)
    button("ESPORTA JSON",func():save_dialog("astra-mission.json",output.text),box)
    button("ESPORTA REGISTRAZIONE CSV",func():
        var data=await request("/desktop/recording")
        var text="time_s,phase,altitude_m,speed_m_s,mass_kg,load_factor_g,dynamic_pressure_Pa\n"
        for s in data.get("samples",[]):
            text+="%s,%s,%s,%s,%s,%s,%s\n"%[str(s.get("time_s","")),str(s.get("phase","")),str(s.get("altitude_m","")),str(s.get("speed_m_s","")),str(s.get("mass_kg","")),str(s.get("load_factor_g","")),str(s.get("dynamic_pressure_Pa",""))]
        save_dialog("astra-mission.csv",text),box)
    var replay_slider=HSlider.new()
    replay_slider.min_value=0;replay_slider.max_value=1
    box.add_child(replay_slider)
    button("CARICA REPLAY TELEMETRICO",func():
        await request("/desktop/pause",{})
        var data=await request("/desktop/recording")
        replay_samples=data.get("samples",[])
        replay_slider.max_value=maxi(0,replay_samples.size()-1),box)
    replay_slider.value_changed.connect(func(value):
        if replay_samples.is_empty():return
        replay_index=int(value)
        var sample=replay_samples[replay_index]
        var replay_state=state.duplicate(true)
        for key in sample:
            if key!="visual" and sample[key]!=null:replay_state[key]=sample[key]
        if sample.has("visual"):scene.set_snapshot({"state":replay_state,"visual":sample.visual})
        output.text=JSON.stringify(sample,"  ")
        widgets.note.text="REPLAY TELEMETRICO · "+str(sample.get("time_s",0))+" s · il motore fisico è in pausa")
    button("TORNA ALLO STATO DEL MOTORE",func():replay_index=-1;poll(),box)

func show_controller():
    var box=window_panel("ASTRA · Controller / HOTAS / Pedali")
    box.add_child(label_text("Il collegamento non arma i comandi. Rilascia gli stick prima di armare.",12))
    var devices=Input.get_connected_joypads()
    for slot in [["Primario", "primary"],["Manetta separata","throttle_device"],["Pedali separati","pedals_device"]]:
        box.add_child(label_text(slot[0],12))
        var list=OptionButton.new()
        list.add_item("Nessuno");list.set_item_metadata(0,-1)
        for id in devices:
            list.add_item(Input.get_joy_name(id)+" · "+str(id))
            list.set_item_metadata(list.item_count-1,id)
            if id==pilot.get(slot[1]):list.select(list.item_count-1)
        list.item_selected.connect(func(index):
            var previous_kind=pilot.config.input_kind
            if not pilot.assign_device(slot[1],list.get_item_metadata(index)):
                for j in range(list.item_count):
                    if list.get_item_metadata(j)==pilot.get(slot[1]):list.select(j)
                widgets.note.text="Dispositivo già assegnato: manetta e pedali richiedono periferiche distinte."
            elif previous_kind!=pilot.config.input_kind:
                box.get_parent().get_parent().get_parent().queue_free();show_controller.call_deferred())
        box.add_child(list)
    var profile_row=HBoxContainer.new();box.add_child(profile_row)
    button("PROFILO T.FLIGHT HOTAS X · PC",func():
        pilot.apply_profile(InputClass.hotas_profile());pilot.save_profile()
        box.get_parent().get_parent().get_parent().queue_free();show_controller(),profile_row)
    box.add_child(label_text("HOTAS X: selettore PC, preset automatico. Un solo dispositivo Primario include stick e manetta.
Assi e pulsanti mostrati da 0: pulsante fisico 1 = indice 0. Usa RILEVA se il driver cambia ordine.",12))
    var input_kind=OptionButton.new();input_kind.add_item("Xbox / gamepad");input_kind.add_item("HOTAS · manetta assoluta sul Primario")
    input_kind.select(1 if pilot.config.input_kind=="hotas" else 0);box.add_child(input_kind)
    var throttle_invert=CheckBox.new();throttle_invert.text="Inverti manetta assoluta";throttle_invert.button_pressed=pilot.config.throttle_inverted;box.add_child(throttle_invert)
    var fields={}
    for setting in [["deadzone","Zona morta",0,.45],["expo","Esponenziale",0,1],["smoothing_s","Filtro · s",.001,.5],["sensitivity","Sensibilità stick",.25,2.5],["throttle_rate_pct_s","Velocità manetta · %/s",10,400],["orbital_slew_deg_s","Velocità riferimento orbitale · °/s",5,180],["roll_axis","Asse roll",0,15],["pitch_axis","Asse pitch",0,15],["yaw_axis","Asse yaw",0,15],["throttle_axis","Asse manetta",0,15],["pause_button","Pulsante pausa (HOTAS)",-1,20],["gnc_button","Pulsante GNC (HOTAS)",-1,20],["arm_button","Pulsante arma/disarma (HOTAS)",-1,20],["brakes_button","Pulsante freni",-1,20],["sas_toggle_button","Pulsante SAS (indice da 0)",-1,20],["sas_next_button","Pulsante prossimo preset (−1 disabilita; 8 R3)",-1,20]]:
        fields[setting[0]]=numeric(box,setting[1],pilot.config[setting[0]],setting[2],setting[3])
        if str(setting[0]).ends_with("_axis") or str(setting[0]).ends_with("_button"):fields[setting[0]].step=1
        if str(setting[0]).ends_with("_axis"):
            button("RILEVA · "+setting[1],func():
                if pilot.primary not in Input.get_connected_joypads():return
                pilot.disarm();controller_learn_axis=setting[0];controller_learn_editor=fields[setting[0]]
                controller_learn_baseline=[]
                for axis_id in range(16):controller_learn_baseline.append(Input.get_joy_axis(pilot.primary,axis_id)),box)
    var curve=OptionButton.new();curve.add_item("Lineare");curve.set_item_metadata(0,"linear")
    curve.add_item("Esponenziale · fine al centro");curve.set_item_metadata(1,"exponential")
    curve.select(1 if pilot.config.curve=="exponential" else 0);box.add_child(curve)
    var inverted=CheckBox.new();inverted.text="Inverti pitch";inverted.button_pressed=bool(pilot.config.invert_pitch);box.add_child(inverted)
    var status=label_text("DISARMATO",13,Color(.6,.8,1));box.add_child(status)
    var live=label_text("",12);box.add_child(live)
    var monitor=Timer.new();monitor.wait_time=.1;box.add_child(monitor)
    monitor.timeout.connect(func():
        var axes=pilot.raw_axes()
        var raw=[];var pressed_buttons=[]
        if pilot.primary in Input.get_connected_joypads():
            for axis_id in range(6):raw.append("%d: %.2f"%[axis_id,Input.get_joy_axis(pilot.primary,axis_id)])
            for button_id in range(20):
                if Input.is_joy_button_pressed(pilot.primary,button_id):pressed_buttons.append(str(button_id))
        live.text=("ARMATO" if pilot.armed else "DISARMATO")+" · RT/LT %.0f %% · R/P/Y %.2f / %.2f / %.2f\nAPI %.1f ms · %s"%[pilot.throttle,axes.x,axes.y,axes.z,pilot_rtt_ms,"in attesa di spinta" if not state.get("mission_started",false) else "in volo"]
        live.text+="\nAssi grezzi: "+", ".join(raw)+"\nPulsanti premuti: "+", ".join(pressed_buttons)+("\nMUOVI SOLO L’ASSE DA ASSEGNARE" if controller_learn_axis!="" else "")
        if pilot_error!="":live.text+="\n"+pilot_error)
    monitor.start()
    button("PROFILO XBOX · RISPOSTA PRONTA",func():
        pilot.apply_profile(InputClass.DEFAULT_CONFIG.duplicate(true));pilot.save_profile()
        for key in fields:fields[key].set_value_no_signal(pilot.config[key])
        curve.select(1 if pilot.config.curve=="exponential" else 0)
        inverted.set_pressed_no_signal(bool(pilot.config.invert_pitch))
        input_kind.select(0);throttle_invert.set_pressed_no_signal(pilot.config.throttle_inverted)
        status.text="Profilo reattivo salvato. Calibra il centro a stick rilasciati, poi arma.",box)
    button("SALVA PROFILO PER QUESTO VEICOLO",func():
        var profile=pilot.config.duplicate(true)
        for key in fields:profile[key]=fields[key].value
        profile.input_kind="hotas" if input_kind.selected==1 else "gamepad"
        profile.throttle_inverted=throttle_invert.button_pressed
        profile.curve=str(curve.get_item_metadata(curve.selected))
        profile.invert_pitch=inverted.button_pressed
        if pilot.apply_profile(profile):pilot.save_profile();status.text="Profilo salvato · "+vehicle
        else:status.text="Profilo non valido",box)
    button("CALIBRA CENTRO · STICK RILASCIATI",func():pilot.calibrate();status.text="Centro registrato. Calibrazione terminata.",box)
    button("CALIBRA ESCURSIONE · MUOVI TUTTI GLI ASSI",func():
        status.text="Muovi gli assi fino ai limiti, poi premi TERMINA." if pilot.start_calibration() else "Seleziona un controller",box)
    button("TERMINA CALIBRAZIONE",func():pilot.finish_calibration();status.text="Calibrazione salvata e terminata.",box)
    button("ESPORTA PROFILO JSON",func():save_dialog("astra-controller.json",JSON.stringify(pilot.config,"  ")),box)
    button("IMPORTA PROFILO JSON",func():
        var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.json ; Profili controller ASTRA"])
        dialog.file_selected.connect(func(path):
            var data=JSON.parse_string(FileAccess.get_file_as_string(path))
            if pilot.apply_profile(data):
                pilot.save_profile();status.text="Profilo importato. Verifica gli assi prima di armare."
            else:status.text="Profilo non valido: nessuna modifica applicata."
            dialog.queue_free())
        dialog.canceled.connect(dialog.queue_free);add_child(dialog);dialog.popup_centered_ratio(.65),box)
    button("ARMA CONTROLLER",func():
        keyboard_active=false
        status.text="ARMATO" if pilot.arm(state) else "Porta gli stick al centro e seleziona un dispositivo",box)
    button("DISARMA / RIPRENDI GNC",func():automatic();status.text="GNC AUTOMATICO",box)
    box.add_child(label_text("Xbox: stick sx roll/pitch · stick dx yaw · RT/LT spinta · LB freni\nCroce direzionale: menu · A conferma · B indietro\nSTART avvio/pausa · X GNC · Y arma/disarma\nGli stick non navigano né modificano i menu.\nDisconnessione/focus perso: GNC automatico.\nManetta assoluta: acquisizione al valore corrente prima di comandare.",13))

func show_graphics():
    var box=window_panel("ASTRA · Grafica nativa",Vector2i(720,570))
    box.add_child(label_text(RenderingServer.get_video_adapter_name(),15))
    box.add_child(label_text("Backend: "+RenderingServer.get_current_rendering_method(),13))
    box.add_child(label_text("FPS UNLIMITED · VSync disattivato",13))
    var preset=OptionButton.new()
    for entry in [["Basso · GPU integrate","low"],["Medio · FSR2","balanced"],["Alto · TAA / SSR","high"],["Ultra · SDFGI","ultra"],["Ultra Cinema · screenshot","cinema"]]:
        preset.add_item(entry[0]);preset.set_item_metadata(preset.item_count-1,entry[1])
    var current_quality=str(view_settings.get("quality","balanced"))
    for i in range(preset.item_count):
        if preset.get_item_metadata(i)==current_quality:preset.select(i);break
    box.add_child(preset)
    preset.item_selected.connect(func(index):
        var selected=str(preset.get_item_metadata(index))
        await request("/desktop/view",{"quality":selected,"resolution_scale":{"low":.65,"balanced":.67,"high":1.0,"ultra":1.15,"cinema":1.5}[selected]})
        await poll())
    for feature in [["enhanced_materials","Microdettagli materiali"],["earthshine","Luce riflessa Terra"]]:
        var control=CheckBox.new();control.text=feature[1];control.button_pressed=bool(view_settings.get(feature[0],true));box.add_child(control)
        control.toggled.connect(func(value):request("/desktop/view",{feature[0]:value}))
    var cinematic=CheckBox.new();cinematic.text="Effetti e camera cinematografica";cinematic.button_pressed=scene.cinematic_effects;box.add_child(cinematic)
    cinematic.toggled.connect(func(value):request("/desktop/view",{"cinematic_effects":value}))
    var sound=CheckBox.new();sound.text="Suoni di bordo · propulsione / motori";sound.button_pressed=scene.effects.audio_enabled;box.add_child(sound)
    sound.toggled.connect(func(value):request("/desktop/view",{"audio_enabled":value}))
    var volume=numeric(box,"Volume suoni di bordo",scene.effects.audio_volume,0,1)
    volume.value_changed.connect(func(value):request("/desktop/view",{"audio_volume":value}))
    var exposure=numeric(box,"Esposizione",scene.environment.tonemap_exposure,.2,3)
    exposure.value_changed.connect(func(value):request("/desktop/view",{"exposure":value}))
    var nebula=numeric(box,"Nebulosa",.9,0,2)
    nebula.value_changed.connect(func(value):request("/desktop/view",{"nebula_strength":value}))
    var scale=numeric(box,"Risoluzione 3D · scala",get_viewport().scaling_3d_scale,.5,1.5)
    scale.value_changed.connect(func(value):request("/desktop/view",{"resolution_scale":value}))
    var eye=CheckBox.new();eye.text="Adattamento esposizione · Forward+";eye.button_pressed=scene.camera.attributes.auto_exposure_enabled;box.add_child(eye)
    eye.toggled.connect(func(value):request("/desktop/view",{"auto_exposure":value}))
    var dof=CheckBox.new();dof.text="Profondità di campo fotografica · Forward+";dof.button_pressed=scene.camera.attributes.dof_blur_far_enabled;box.add_child(dof)
    dof.toggled.connect(func(value):request("/desktop/view",{"depth_of_field":value}))
    var shadows=CheckBox.new();shadows.text="Ombre dinamiche";shadows.button_pressed=scene.light.shadow_enabled;box.add_child(shadows)
    shadows.toggled.connect(func(value):scene.light.shadow_enabled=value)
    var notes=label_text("Forward+: HDR, glow e SSAO; riflessi SSR nei profili high/ultra.\nCompatibility: illuminazione PBR e ombre, costo ridotto.\nI profili di avvio scelgono anche il backend; nessuna alterazione della fisica.",12)
    notes.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(notes)

func show_assets():
    var box=window_panel("ASTRA · Asset 3D",Vector2i(760,590))
    box.add_child(label_text("Il modello grafico non sostituisce i parametri del profilo fisico.",13))
    var selection=OptionButton.new()
    selection.add_item("Automatico · modelli pre-realizzati")
    selection.set_item_metadata(0,"auto")
    for model in scene.assets.models.values():
        if model.category not in [vehicle,scenario]:continue
        selection.add_item(model.name)
        selection.set_item_metadata(selection.item_count-1,model.id)
    box.add_child(selection)
    var note=label_text("",12);note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(note)
    var refresh=func():
        var item=scene.assets.models.get(scene.asset_choice,scene.active_asset)
        note.text=str(item.get("name","GLB importato"))+"\n"+str(item.get("source",""))+" · "+str(item.get("license",""))+"\n"+str(item.get("source_url",""))
    refresh.call()
    selection.item_selected.connect(func(index):
        await request("/desktop/view",{"model":selection.get_item_metadata(index)})
        await poll()
        refresh.call())
    button("IMPORTA FILE .GLB",func():
        var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.glb ; glTF Binary"])
        dialog.file_selected.connect(func(path):scene.asset_choice="custom";scene.selected_asset=path;scene.model_key="";dialog.queue_free())
        dialog.canceled.connect(dialog.queue_free);add_child(dialog);dialog.popup_centered_ratio(.7),box)
    button("RIPRISTINA MODELLO PREDEFINITO",func():request("/desktop/view",{"model":"auto"}),box)
    button("CREDITI E LICENZE",func():
        var credits=window_panel("ASTRA · Crediti degli asset",Vector2i(900,700))
        var text=output_editor(credits,600)
        var path=asset_path.get_base_dir().path_join("ASSET-CREDITS.txt")
        if not FileAccess.file_exists(path):path=asset_path.get_base_dir().path_join("ASSET-CREDITS.md")
        text.text=FileAccess.get_file_as_string(path),box)

func show_celestial():
    var box=window_panel("ASTRA · Sistema solare / Progettazione missione",Vector2i(900,740))
    var date=LineEdit.new();date.text="2026-10-28T00:00:00Z";box.add_child(date)
    var target=OptionButton.new()
    for body in ["moon","earth","mercury","venus","mars","jupiter","saturn","uranus","neptune"]:target.add_item(body)
    box.add_child(target)
    var output=output_editor(box,420)
    button("EFFEMERIDI / CATALOGO",func():
        var reply=await request("/celestial?date="+date.text.uri_encode())
        if not reply.has("error"):scene.show_solar_map(reply)
        output.text=JSON.stringify(reply,"  "),box)
    button("OSSERVA CORPO · SUPERFICIE 3D",func():
        var reply=await request("/celestial?date="+date.text.uri_encode())
        if not reply.has("error"):scene.inspect_body(reply,target.get_item_text(target.selected))
        output.text="Ispezione superficie · texture NASA / Solar System Scope.\n"+JSON.stringify(reply.get("validity","")),box)
    box.add_child(label_text("Mappa: distanze proporzionali; corpi ingranditi per leggibilità. Le orbite mostrate sono guide circolari di riferimento; effemeridi e targeting sono nei risultati SI.",11))
    button("TORNA AL VEICOLO",func():scene.hide_solar_map(),box)
    button("PIANIFICA TRASFERIMENTO",func():
        output.text="Targeting in corso…"
        var reply=await request("/transfer?target="+target.get_item_text(target.selected)+"&date="+date.text.uri_encode())
        output.text=JSON.stringify(reply,"  "),box)
    var elapsed_field=numeric(box,"Tempo propagato · s",0,0,1e9)
    button("PROPAGA STATO DEL TRASFERIMENTO",func():
        var reply=await request("/transfer/state?target="+target.get_item_text(target.selected)+"&date="+date.text.uri_encode()+"&elapsed_s="+str(elapsed_field.value))
        scene.show_transfer_state(reply)
        output.text=JSON.stringify(reply,"  "),box)
    button("ESPORTA PIANO JSON",func():save_dialog("astra-transfer.json",output.text),box)

func show_game_missions_current():
    var index=mission_selection.selected
    show_game_missions(str(mission_selection.get_item_metadata(index)) if index>=0 else "space")

func show_game_missions(kind):
    var board=MissionBoard.new()
    board.setup(self,kind,game_language)

func mission_text(key):
    return str(mission_messages.get(game_language,{}).get(key,key))

func game_action(action,payload={},window=null):
    if action!="checkpoint" or payload.get("action")!="save":
        keyboard_active=false;pilot.disarm();latest_pilot_command={}
    var reply=await request("/desktop/game/"+action,payload)
    if reply.has("error"):
        report_result(reply)
        return
    if action=="checkpoint" and payload.get("action")=="save":
        widgets.note.text=mission_text("saved")
        await poll()
        return
    game_result_seen=""
    if is_instance_valid(window):window.queue_free()
    apply_game_start(reply)
    await request("/desktop/play",{})
    await poll()

func apply_game_start(reply):
    game_state=reply.get("game",{})
    game_career=reply.get("career",{})
    state=reply.get("state",{})
    desktop=reply.get("desktop",{})
    vehicle=str(state.get("vehicle","space"));scenario=str(state.get("scenario","mission"))
    free_mode=true;game_mode=true;game_result_seen=""
    mission_selection.select(0 if vehicle=="space" else 1 if vehicle=="aircraft" else 2)
    pilot.load_profile(vehicle);keyboard_active=true;replay_index=-1
    keyboard_throttle=float(state.get("command",{}).get("throttle_pct",0))
    fill_models();scene.asset_choice="auto";scene.selected_asset="";scene.catalogue_asset={}

func start_game_mission(mission_id,win):
    keyboard_active=false;pilot.disarm();latest_pilot_command={}
    var reply=await request("/desktop/game/start",{"mission_id":mission_id,"language":game_language})
    if reply.has("error"):
        widgets.note.text=str(reply.error)
        return
    apply_game_start(reply)
    if is_instance_valid(win):win.queue_free()
    var tutorial=str(game_state.get("tutorial",""))
    if tutorial!="":
        var box=window_panel(mission_text("tutorial"),Vector2i(620,360))
        var tutorial_window=box.get_parent().get_parent().get_parent()
        box.add_child(label_text(mission_text("tutorial"),22,Color(.55,.85,1)))
        var explanation=label_text(tutorial,16);explanation.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(explanation)
        box.add_child(label_text(mission_text("controls"),13))
        button(mission_text("resume"),func():tutorial_window.queue_free();request("/desktop/play",{}),box)
    else:await request("/desktop/play",{})
    await poll()

func show_python(proof=null):
    if proof!=null:
        var box=window_panel("ASTRA · GNC PYTHON / PROVA REALE",Vector2i(665,780))
        var window=box.get_parent().get_parent().get_parent()
        window.position=Vector2i(18,95)
        box.add_child(label_text("SDK "+str(proof.client_version)+" · CONTROLLO IN CICLO CHIUSO",13,Color(.55,.8,1)))
        var script=json_editor(box,{},430);script.text=proof.code;script.add_theme_font_size_override("font_size",12)
        box.add_child(label_text("RISULTATO MISURATO · STESSO VEICOLO NELLA VISTA 3D",11,Color(.55,.8,1)))
        var output=output_editor(box,130);output.text=proof.summary
        box.add_child(label_text("Clock esterno Python · motore e renderer condividono lo stato",11))
        return
    var box=window_panel("ASTRA · API Python desktop",Vector2i(880,650))
    box.add_child(label_text("API attiva: "+api_url+"/api/v1",15))
    var code="from astra_sdk import AstraClient\n\nclient = AstraClient('"+api_url+"')\nprint(client.status())\nclient.pause()\nclient.reset('space', 'orbital', advanced_models=True)\nclient.launch()\nfor _ in range(100):\n    client.command(mode='python', throttle_pct=0)\n    state = client.step(0.1)\n    print(state['time_s'], state['altitude_m'])\n"
    var editor=json_editor(box,{},300);editor.text=code
    button("COPIA CODICE",func():DisplayServer.clipboard_set(editor.text),box)
    button("CEDI IL CLOCK AL CLIENT PYTHON",func():request("/desktop/clock",{"owner":"external"}),box)
    button("RIPRENDI IL CLOCK DESKTOP · IN PAUSA",func():request("/desktop/clock",{"owner":"desktop"}),box)
    box.add_child(label_text("Il primo client.step() mette in pausa il clock automatico.\nL'API e il controllo Python restano attivi anche con la finestra 3D in background.",13))

func capture_python_proof():
    var proof=JSON.parse_string(FileAccess.get_file_as_string(python_proof_data))
    if proof==null or absf(float(proof.final.time_s)-float(state.get("time_s",0)))>=.001:
        push_error("Python proof does not match the current simulation state");get_tree().quit(1);return
    get_viewport().gui_embed_subwindows=true
    show_python(proof)
    scene.camera.h_offset=-.7
    await get_tree().create_timer(1.2).timeout
    await RenderingServer.frame_post_draw
    var frame=get_viewport().get_texture().get_image()
    var saved=frame.save_png(python_proof_path+".png")
    if saved!=OK:push_error("Python proof PNG could not be saved");get_tree().quit(1);return
    var report={"time_s":state.time_s,"vehicle":state.vehicle,"mode":state.command.mode,"clock_owner":desktop.clock_owner,"altitude_m":state.altitude_m,"script_output_matches_state":true,"fps":Engine.get_frames_per_second()}
    var file=FileAccess.open(python_proof_path+".json",FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "))
    get_tree().quit()

func save_career():
    var file=ConfigFile.new()
    for key in career:file.set_value("career",key,career[key])
    file.save("user://career.cfg")

func show_career():
    game_career=await request("/desktop/game/career")
    var box=window_panel("ASTRA · Carriera / Progressione",Vector2i(760,700))
    box.add_child(label_text("CENTRO OPERATIVO · avanzamento salvato localmente",13,Color(.55,.8,1)))
    box.add_child(label_text("Crediti  ¤ %s     Reputazione  %s     Scienza  %s"%[
        str(game_career.get("credits",0)),str(game_career.get("reputation",0)),str(game_career.get("science",0))],20))
    box.add_child(label_text("Operazioni completate  %s / lanci  %s"%[
        str(game_career.get("missions_completed",0)),str(game_career.get("launches",0))],14))
    box.add_child(HSeparator.new())
    box.add_child(label_text("STRUTTURE · upgrade finanziati dalla carriera",14,Color(.55,.8,1)))
    var facilities=game_career.get("facilities",{"hangar":1,"mission_control":1,"research":1})
    for entry in [["hangar","Hangar"],["mission_control","Centro di controllo"],["research","Centro ricerca"]]:
        var level=int(facilities.get(entry[0],1))
        button(str(entry[1])+" · livello "+str(level)+(" · MAX" if level>=3 else " · upgrade ¤ "+str(level*5000)),func():
            var reply=await request("/desktop/game/career/upgrade",{"facility":entry[0]})
            if reply.has("error"):widgets.note.text=str(reply.error)
            else:game_career=reply;show_career(),box)
    box.add_child(HSeparator.new())
    box.add_child(label_text("RICERCA · sblocchi di carriera",14,Color(.55,.8,1)))
    var techs=game_career.get("unlocked_technologies",[])
    for entry in [["orbital_operations","Operazioni orbitali",15],["planetary_science","Scienza planetaria",30],["precision_navigation","Navigazione di precisione",45]]:
        button(str(entry[1])+ (" · SBLOCCATA" if techs.has(entry[0]) else " · "+str(entry[2])+" punti scienza"),func():
            var reply=await request("/desktop/game/career/unlock",{"technology":entry[0]})
            if reply.has("error"):widgets.note.text=str(reply.error)
            else:game_career=reply;show_career(),box)
    box.add_child(label_text("Gli obiettivi di missione usano telemetria, navigazione, batteria e velocità di contatto prodotti dal simulatore.",11))

func show_game_result():
    if not game_state.get("active",false):return
    var mission=game_state.mission
    var succeeded=bool(game_state.get("complete",false))
    var box=window_panel(mission_text("result"),Vector2i(780,640))
    var win=box.get_parent().get_parent().get_parent()
    box.add_child(label_text(mission_text("completed") if succeeded else mission_text("failed"),24,Color(.55,.95,.77) if succeeded else Color(1,.66,.44)))
    box.add_child(label_text(str(mission.title),18))
    var medal=str(game_state.get("medal",""))
    if medal!="":box.add_child(label_text("◇  "+mission_text(medal),22,Color(1,.81,.41)))
    if game_state.get("failure_reason","")!="":
        var reason=label_text(mission_text(str(game_state.failure_reason)));reason.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;box.add_child(reason)
    box.add_child(label_text(mission_text("measured"),12,Color(.4,.75,1)))
    var metrics=game_state.get("metrics",{"elapsed_s":game_state.get("elapsed_s",0),"distance_m":game_state.get("distance_m",0)})
    var units={"elapsed_s":"s","distance_m":"m","resource_pct":"%","touchdown_speed_m_s":"m/s","max_altitude_m":"m","max_load_factor_g":"g","min_resource_pct":"%","relative_range_m":"m","relative_speed_m_s":"m/s"}
    for key in metrics:
        if metrics[key] is float or metrics[key] is int:
            box.add_child(label_text(mission_text(key)+"  "+format_number(metrics[key])+" "+units.get(key,""),14))
    for objective in game_state.get("objective_progress",[]):
        box.add_child(label_text(("✓  " if objective.get("complete",false) else "○  ")+str(objective.label),13))
    if succeeded:
        var reward=game_state.get("earned_reward",mission.reward)
        box.add_child(label_text(mission_text("reward")+"  ¤ %d  ·  REP %d  ·  SCI %d"%[int(reward.get("credits",0)),int(reward.get("reputation",0)),int(reward.get("science",0))],18,Color(.6,.9,.8)))
        var next_button=button(mission_text("next_mission"),func():game_action("next",{},win),box)
        next_button.disabled=str(game_state.get("next_mission_id",""))==""
    button(mission_text("retry"),func():game_action("retry",{},win),box)
    if game_state.get("checkpoint_available",false):
        button(mission_text("restore"),func():game_action("checkpoint",{"action":"restore"},win),box)
    if game_state.get("hint","")!="":box.add_child(label_text(mission_text("hint")+": "+str(game_state.hint),13))
    button(mission_text("board_action"),func():win.queue_free();show_game_missions(vehicle),box)

func smoke_capture(path):
    await RenderingServer.frame_post_draw
    var image=get_viewport().get_texture().get_image()
    if image!=null:image.save_png(path+".png")
    frame_times.sort()
    var report={"native":true,"browser_required":false,"renderer":RenderingServer.get_current_rendering_method(),
        "adapter":RenderingServer.get_video_adapter_name(),"frames":renderer_frames,
        "fps":Engine.get_frames_per_second(),"frame_p95_ms":frame_times[int(frame_times.size()*.95)] if not frame_times.is_empty() else 0,
        "solvers":studies.size(),"science_disciplines":state.get("science",{}).get("disciplines",{}).size(),
        "api_url":api_url,"vehicle":state.get("vehicle"),"scenario":state.get("scenario"),
        "time_s":state.get("time_s"),"physics_clock_owner":desktop.get("clock_owner"),
        "screenshot_saved":image!=null}
    var file=FileAccess.open(path+".json",FileAccess.WRITE)
    if file!=null:file.store_string(JSON.stringify(report,"  "))
    print("ASTRA NATIVE SMOKE: "+JSON.stringify(report))
    get_tree().quit()

func smoke_suite():
    var results=[]
    var asset_results=[]
    for pair in [["space","mission"],["space","orbital"],["space","planetary"],["aircraft","mission"],["drone","mission"]]:
        await request("/reset",{"vehicle":pair[0],"scenario":pair[1],"advanced_models":true})
        await request("/launch",{})
        await request("/step",{"dt_s":.2})
        await get_tree().create_timer(.4).timeout
        await poll()
        await get_tree().create_timer(1.2).timeout
        await RenderingServer.frame_post_draw
        var image=get_viewport().get_texture().get_image()
        var name=pair[0]+"-"+pair[1]
        if image!=null:image.save_png(smoke_suite_path+"-"+name+".png")
        var vertical=true
        var dimensions=Vector3.ZERO
        if pair==["space","mission"] and scene.model_root.get_child_count()>0:
            dimensions=scene.assets.get_bounds(scene.model_root.get_child(0)).size
            vertical=dimensions.y>dimensions.x*2 and dimensions.y>dimensions.z*2 and scene.vehicle_root.basis.y.normalized().dot(Vector3.UP)>.98
        results.append({"name":name,"time_s":state.get("time_s"),"disciplines":state.get("science",{}).get("disciplines",{}).size(),"screenshot":image!=null,"asset_id":scene.active_asset_id,"loaded":scene.last_model_import_ok,"launch_vertical":vertical,"asset_dimensions_m":[dimensions.x,dimensions.y,dimensions.z]})
    for kind in ["space","aircraft","drone"]:
        await request("/reset",{"vehicle":kind,"advanced_models":true})
        while pending:await get_tree().process_frame
        await poll()
        await get_tree().create_timer(1).timeout
        await RenderingServer.frame_post_draw
        var shot=get_viewport().get_texture().get_image()
        if shot!=null:shot.save_png(smoke_suite_path+"-asset-"+kind+".png")
        asset_results.append({"vehicle":kind,"loaded":scene.last_model_import_ok,"path":scene.selected_asset,"screenshot":shot!=null})
        scene.asset_choice="auto";scene.selected_asset="";scene.model_key=""
    var secondary=[]
    for pair in [["aircraft","corvo-t2"],["drone","merlo-h6"],["space","dardo-lifting-body"]]:
        await request("/reset",{"vehicle":pair[0],"model_id":pair[1],"advanced_models":true})
        while pending:await get_tree().process_frame
        await poll()
        await get_tree().create_timer(1).timeout
        await RenderingServer.frame_post_draw
        var shot=get_viewport().get_texture().get_image()
        if shot!=null:shot.save_png(smoke_suite_path+"-"+pair[1]+".png")
        var vertical=true
        if pair[0]=="space" and scene.model_root.get_child_count()>0:
            var shape=scene.assets.get_bounds(scene.model_root.get_child(0)).size
            vertical=shape.y>shape.x*2 and shape.y>shape.z*2
        secondary.append({"model_id":pair[1],"asset_id":scene.active_asset_id,"loaded":scene.last_model_import_ok,"rotor_pivots":scene.animated_rotors.size(),"launch_vertical":vertical})
    var free_results=[]
    for kind in ["space","aircraft","drone"]:
        await change_mission(6 if kind=="space" else 8 if kind=="aircraft" else 9)
        while pending:await get_tree().process_frame
        await poll()
        assert(free_mode and state.command.mode=="manual" and not desktop.running)
        await toggle_play()
        await get_tree().create_timer(.15).timeout
        await toggle_play()
        await poll()
        assert(state.command.mode=="manual")
        free_results.append({"vehicle":kind,"mode":desktop.play_mode,"manual":state.command.mode=="manual","time_s":state.time_s})
    var globe_results=[]
    for mode in ["mission","planetary"]:
        await request("/reset",{"vehicle":"space","scenario":mode,"advanced_models":true})
        while pending:await get_tree().process_frame
        await poll()
        await request("/desktop/view",{"distance_m":22000000 if mode=="mission" else 7000000,"elevation_deg":45,"show_ui":false})
        await poll();await get_tree().create_timer(2).timeout
        await RenderingServer.frame_post_draw
        var globe=get_viewport().get_texture().get_image()
        if globe!=null:globe.save_png(smoke_suite_path+"-globe-"+mode+".png")
        assert(not scene.ground_root.visible and scene.sky_material.get_shader_parameter("planet_visible"))
        globe_results.append({"scenario":mode,"local_patch_hidden":not scene.ground_root.visible,"spherical_sky":true,"camera_distance_m":scene.distance,"screenshot":globe!=null})
    await request("/reset",{"vehicle":"aircraft","advanced_models":true})
    await request("/desktop/view",{"distance_m":null,"show_ui":true})
    while pending:await get_tree().process_frame
    await poll()
    for key in ["attitude","position","flight"]:detail_widgets[key].toggle.button_pressed=true
    await get_tree().create_timer(.4).timeout
    assert(detail_widgets.flight.values.size()>12)
    await RenderingServer.frame_post_draw
    var instruments=get_viewport().get_texture().get_image()
    if instruments!=null:instruments.save_png(smoke_suite_path+"-instruments.png")
    for key in detail_widgets:detail_widgets[key].toggle.button_pressed=false
    show_laboratory()
    await get_tree().create_timer(.5).timeout
    for child in get_children():
        if child is Window:child.queue_free()
    show_controller()
    await get_tree().create_timer(.4).timeout
    for child in get_children():
        if child is Window:child.queue_free()
    show_data_lab()
    await get_tree().create_timer(.4).timeout
    for child in get_children():
        if child is Window:child.queue_free()
    var report={"native":true,"renderer":RenderingServer.get_current_rendering_method(),"adapter":RenderingServer.get_video_adapter_name(),"resolution_scale":get_viewport().scaling_3d_scale,"scaling_3d_mode":get_viewport().scaling_3d_mode,"cases":results,"secondary_models":secondary,"asset_imports":asset_results,"free_flight":free_results,"globes":globe_results,"detailed_instruments":detail_widgets.flight.values.size(),"solvers":studies.size(),"browser_required":false,"procedural_vehicles":false}
    var file=FileAccess.open(smoke_suite_path+".json",FileAccess.WRITE)
    if file!=null:file.store_string(JSON.stringify(report,"  "))
    print("ASTRA NATIVE SUITE: "+JSON.stringify(report))
    get_tree().quit()
