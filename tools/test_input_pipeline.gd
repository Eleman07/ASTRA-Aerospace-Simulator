extends SceneTree

const Main=preload("res://main.gd")
const NativeInput=preload("res://native_input.gd")
const MenuWindow=preload("res://menu_window.gd")

class VirtualPilot extends NativeInput:
    var axis=Vector3.ZERO
    var trigger=0.0
    func sample(dt,state):
        return advance(dt,state,axis,trigger,0,false)

class FlightUI extends Main:
    var play_count=0
    var sas_count=0
    var sas_cycle_count=0
    var gnc_count=0
    func _ready():pass
    func _process(_dt):pass
    func toggle_play():play_count+=1
    func toggle_sas():sas_count+=1
    func cycle_sas(_direction=1):sas_cycle_count+=1
    func automatic():gnc_count+=1;pilot.disarm()

func require(condition,message):
    if not condition:
        push_error(message);quit(1)
    return condition

func _initialize():
    run.call_deferred()

func run():
    var flight=FlightUI.new()
    root.add_child(flight)
    flight.configure_controller_ui()
    for action in InputMap.get_actions():
        if str(action).begins_with("ui_"):
            for binding in InputMap.action_get_events(action):
                if not require(not binding is InputEventJoypadMotion,"stick still bound to "+str(action)):return
    for pair in [["ui_up",JOY_BUTTON_DPAD_UP],["ui_down",JOY_BUTTON_DPAD_DOWN],["ui_left",JOY_BUTTON_DPAD_LEFT],["ui_right",JOY_BUTTON_DPAD_RIGHT]]:
        var has_dpad=false
        var has_keyboard=false
        for binding in InputMap.action_get_events(pair[0]):
            if binding is InputEventJoypadButton and binding.button_index==pair[1]:has_dpad=true
            if binding is InputEventKey:has_keyboard=true
        if not require(has_dpad and has_keyboard,"D-pad or keyboard arrows removed from "+pair[0]):return
    var controls=VBoxContainer.new();root.add_child(controls)
    for field in [[.08,0,.45],[.012,.001,.5],[1.8,.25,2.5],[140.0,10,400],[90.0,5,180]]:
        var editor=flight.numeric(controls,"test",field[0],field[1],field[2])
        if not require(is_equal_approx(editor.value,field[0]),"opening settings rounded a controller value"):return
    var pilot=VirtualPilot.new()
    pilot.apply_profile(NativeInput.DEFAULT_CONFIG.duplicate(true))
    pilot.armed=true;pilot.primary=0;pilot.trigger=1.0;pilot.axis=Vector3.RIGHT
    flight.pilot=pilot
    flight.state={"scenario":"orbital"};flight.desktop={"clock_owner":"desktop"}
    # A reply blocked for 800 ms must not slow local throttle or references.
    flight.pilot_pending=true
    for i in range(80):flight.latest_pilot_command=flight.collect_pilot(.01)
    if not require(is_equal_approx(flight.latest_pilot_command.throttle_pct,100.0),"HTTP wait discarded input time"):return
    if not require(flight.latest_pilot_command.attitude_torque_body_fraction[0]>.9,"orbital input stopped during HTTP wait"):return
    pilot.axis=Vector3.LEFT
    flight.latest_pilot_command=flight.collect_pilot(.05)
    if not require(flight.latest_pilot_command.roll_deg< -29,"latest direction must replace stale commands"):return
    var spin=flight.numeric(controls,"flight sensitivity",1.5,.25,2.5)
    spin.get_line_edit().grab_focus()
    for axis in [JOY_AXIS_LEFT_X,JOY_AXIS_LEFT_Y,JOY_AXIS_RIGHT_X,JOY_AXIS_RIGHT_Y,JOY_AXIS_TRIGGER_LEFT,JOY_AXIS_TRIGGER_RIGHT]:
        for value in [-1.0,1.0,0.0]:
            var motion=InputEventJoypadMotion.new();motion.device=0;motion.axis=axis;motion.axis_value=value
            Input.parse_input_event(motion)
            await process_frame
            if not require(is_equal_approx(spin.value,1.5),"analog motion changed a menu value"):return
    var focused=Button.new();focused.text="MENU 1";controls.add_child(focused)
    var second=Button.new();second.text="MENU 2";controls.add_child(second)
    focused.focus_neighbor_bottom=second.get_path();second.focus_neighbor_top=focused.get_path()
    focused.grab_focus()
    var button_calls=[0]
    second.pressed.connect(func():button_calls[0]+=1)
    await process_frame
    var down=InputEventJoypadButton.new();down.device=0;down.button_index=JOY_BUTTON_DPAD_DOWN;down.pressed=true
    Input.parse_input_event(down);await process_frame
    down=InputEventJoypadButton.new();down.device=0;down.button_index=JOY_BUTTON_DPAD_DOWN;down.pressed=false
    Input.parse_input_event(down);await process_frame
    if not require(second.has_focus(),"D-pad did not navigate to the next menu button"):return
    var press=InputEventJoypadButton.new();press.device=0;press.button_index=JOY_BUTTON_A;press.pressed=true
    Input.parse_input_event(press)
    await process_frame
    var release=InputEventJoypadButton.new();release.device=0;release.button_index=JOY_BUTTON_A;release.pressed=false
    Input.parse_input_event(release)
    await process_frame
    if not require(flight.play_count==0 and button_calls[0]==1,"A must confirm the menu once without toggling flight (play=%s, GUI=%s, accept=%s, focus=%s)"%[flight.play_count,button_calls[0],InputMap.event_is_action(press,"ui_accept"),root.gui_get_focus_owner()]):return
    press=InputEventJoypadButton.new();press.device=0;press.button_index=JOY_BUTTON_START;press.pressed=true
    Input.parse_input_event(press);await process_frame
    release=InputEventJoypadButton.new();release.device=0;release.button_index=JOY_BUTTON_START;release.pressed=false
    Input.parse_input_event(release);await process_frame
    if not require(flight.play_count==1 and button_calls[0]==1,"Start must toggle flight once without activating the GUI"):return
    for binding in [pilot.config.sas_toggle_button,pilot.config.sas_next_button]:
        var sas_press=InputEventJoypadButton.new();sas_press.device=0;sas_press.button_index=binding;sas_press.pressed=true
        Input.parse_input_event(sas_press);await process_frame
        sas_press=InputEventJoypadButton.new();sas_press.device=0;sas_press.button_index=binding;sas_press.pressed=false
        Input.parse_input_event(sas_press);await process_frame
    if not require(flight.sas_count==1 and flight.sas_cycle_count==1 and button_calls[0]==1,"SAS buttons must route once without activating menus"):return
    spin.get_line_edit().grab_focus()
    var key=InputEventKey.new();key.keycode=KEY_T;key.unicode=116;key.pressed=true
    Input.parse_input_event(key);await process_frame
    if not require(flight.sas_count==1,"typing T must not toggle SAS"):return
    focused.grab_focus()
    key=InputEventKey.new();key.keycode=KEY_T;key.pressed=true
    Input.parse_input_event(key);await process_frame
    if not require(flight.sas_count==2,"T must toggle SAS in flight"):return
    root.gui_embed_subwindows=true
    var menu=MenuWindow.new();root.add_child(menu)
    var menu_controls=VBoxContainer.new();menu.add_child(menu_controls)
    var menu_spin=flight.numeric(menu_controls,"stick must not edit",.012,.001,.5)
    menu.popup_centered(Vector2i(500,300));menu_spin.get_line_edit().grab_focus()
    await process_frame
    var motion=InputEventJoypadMotion.new();motion.device=0;motion.axis=JOY_AXIS_LEFT_X;motion.axis_value=1.0
    Input.parse_input_event(motion);await process_frame
    if not require(is_equal_approx(menu_spin.value,.012),"stick modified a value in a child window"):return
    var cancel=InputEventJoypadButton.new();cancel.device=0;cancel.button_index=JOY_BUTTON_B;cancel.pressed=true
    Input.parse_input_event(cancel);await process_frame;await process_frame
    if not require(not is_instance_valid(menu),"B did not close the menu panel"):return
    pilot.apply_profile(NativeInput.hotas_profile());pilot.armed=true
    for number in [0,1,2,7,8]:
        var hotas_event=InputEventJoypadButton.new();hotas_event.device=0;hotas_event.button_index=number;hotas_event.pressed=true
        Input.parse_input_event(hotas_event);await process_frame
        hotas_event=InputEventJoypadButton.new();hotas_event.device=0;hotas_event.button_index=number;hotas_event.pressed=false
        Input.parse_input_event(hotas_event);await process_frame
    if not require(flight.sas_count==3 and flight.sas_cycle_count==2 and flight.play_count==2 and flight.gnc_count==1,"HOTAS action routing failed"):return
    if not require(button_calls[0]==1,"HOTAS trigger activated Xbox menu action"):return
    print("HOTAS ROUTING PASS: trigger SAS, next preset, brakes isolated, pause and GNC without Xbox menu leakage")
    var hotas_menu=MenuWindow.new();flight.add_child(hotas_menu)
    hotas_menu.hotas_input_router=Callable(flight,"route_hotas_menu_input")
    var hotas_button=Button.new();hotas_button.text="MUST NOT ACTIVATE";hotas_menu.add_child(hotas_button)
    hotas_button.pressed.connect(func():button_calls[0]+=100)
    hotas_menu.popup_centered(Vector2i(400,200));hotas_button.grab_focus();await process_frame
    pilot.armed=true
    var in_menu=InputEventJoypadButton.new();in_menu.device=0;in_menu.button_index=0;in_menu.pressed=true
    Input.parse_input_event(in_menu);await process_frame
    in_menu=InputEventJoypadButton.new();in_menu.device=0;in_menu.button_index=0;in_menu.pressed=false
    Input.parse_input_event(in_menu);await process_frame
    if not require(flight.sas_count==4 and button_calls[0]==1,"HOTAS trigger leaked into child-window GUI"):return
    hotas_menu.queue_free();await process_frame
    flight.desktop={"clock_owner":"external"}
    if not require(flight.collect_pilot(.02).is_empty() and not pilot.armed,"Python clock must retain exclusive control"):return
    print("INPUT PIPELINE PASS: exact settings, no lost time, sticks isolated in root and child menus, D-pad navigates, A confirms, B closes panel, Start toggles once, Python clock exclusive")
    quit()
