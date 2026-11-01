extends Control
## Original ASTRA vector symbols. Positions come only from engine body vectors.
signal toggled
signal mode_selected(mode)

const MODES = [["stability_assist","STB","Stability Assist"], ["prograde","PG","Prograde"],
    ["retrograde","RG","Retrograde"], ["normal","N+","Normal"],
    ["anti_normal","N−","Anti-Normal"], ["radial_in","R−","Radial In"],
    ["radial_out","R+","Radial Out"], ["target","TG","Target"],
    ["anti_target","AT","Anti-Target"], ["maneuver_node","MN","Maneuver Node"]]
var telemetry = {}
var mode_buttons = {}
var toggle_button: Button
var status_label: Label
var center = Vector2(144,137)

func _ready():
    custom_minimum_size=Vector2(288,310)
    size=custom_minimum_size
    mouse_filter=Control.MOUSE_FILTER_IGNORE
    for i in range(MODES.size()):
        var entry=MODES[i]
        var angle=-PI/2.0+TAU*float(i)/MODES.size()
        var control=Button.new()
        control.position=center+Vector2(cos(angle)*112,sin(angle)*90)-Vector2(24,17)
        control.size=Vector2(48,34)
        control.text=entry[1];control.tooltip_text=entry[2]
        control.toggle_mode=true;control.focus_mode=Control.FOCUS_NONE
        control.add_theme_font_size_override("font_size",12)
        control.pressed.connect(func():mode_selected.emit(entry[0]))
        add_child(control);mode_buttons[entry[0]]=control
    toggle_button=Button.new();toggle_button.position=Vector2(48,258);toggle_button.size=Vector2(192,36)
    toggle_button.focus_mode=Control.FOCUS_NONE
    toggle_button.pressed.connect(func():toggled.emit())
    add_child(toggle_button)
    status_label=Label.new();status_label.position=Vector2(6,8);status_label.size=Vector2(276,20)
    status_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
    status_label.add_theme_font_size_override("font_size",11)
    add_child(status_label)
    update_state({})

func update_state(data):
    telemetry=data
    visible=true
    if toggle_button==null:return
    var enabled=bool(data.get("enabled",false))
    toggle_button.text="● SAS ON  [T]" if enabled else "○ SAS OFF  [T]"
    toggle_button.modulate=Color(.46,1,.8) if enabled else Color(.78,.84,.92)
    var mode=str(data.get("mode","stability_assist"))
    status_label.text="INPUT MANUALE · SAS IN ATTESA" if data.get("manual_override",false) else "SAS · "+mode.replace("_"," ").to_upper() if enabled else "GNC AUTO" if data.get("authority")=="gnc" else "STABILIZZAZIONE · SAS OFF"
    for key in mode_buttons:
        mode_buttons[key].visible=key in data.get("available_modes",[])
        mode_buttons[key].set_pressed_no_signal(enabled and key==mode)
    queue_redraw()

func _draw():
    draw_style_box(_background(),Rect2(Vector2.ZERO,size))
    draw_circle(center,63,Color(.035,.075,.12,.96))
    draw_arc(center,63,0,TAU,64,Color(.28,.46,.6),1,true)
    draw_arc(center,40,0,TAU,48,Color(.15,.27,.36),1,true)
    draw_line(center+Vector2(-59,0),center+Vector2(59,0),Color(.18,.33,.43),1,true)
    draw_line(center+Vector2(0,-59),center+Vector2(0,59),Color(.18,.33,.43),1,true)
    for key in telemetry.get("markers",{}):
        var body=telemetry.markers[key].get("direction_body",[1,0,0])
        if body.size()!=3:continue
        var v=Vector3(float(body[0]),float(body[1]),float(body[2])).normalized()
        # Azimuthal projection: forward at center, rear hemisphere at rim.
        var lateral=Vector2(v.y,-v.z)
        if v.x<0 and lateral.length_squared()<0.000001:lateral=Vector2.DOWN
        var angle=acos(clampf(v.x,-1,1))
        var point=center+lateral.normalized()*minf(angle/(PI/2),1.0)*56
        var color=Color(.5,.95,.68) if key in ["prograde","retrograde"] else Color(.7,.65,1) if key in ["normal","anti_normal"] else Color(.35,.8,1) if key in ["radial_in","radial_out"] else Color(1,.72,.36)
        if v.x<0:color.a=.32
        _marker(point,str(key),color)
    draw_line(center+Vector2(-13,0),center+Vector2(-4,0),Color.WHITE,2,true)
    draw_line(center+Vector2(4,0),center+Vector2(13,0),Color.WHITE,2,true)
    draw_line(center+Vector2(0,-4),center+Vector2(0,4),Color.WHITE,2,true)

func _background():
    var style=StyleBoxFlat.new();style.bg_color=Color(.025,.05,.085,.86)
    style.set_corner_radius_all(12);style.border_color=Color(.14,.25,.35);style.set_border_width_all(1)
    return style

func _marker(p,key,color):
    var diamond=PackedVector2Array([p+Vector2(0,-6),p+Vector2(6,0),p+Vector2(0,6),p+Vector2(-6,0),p+Vector2(0,-6)])
    if key in ["target","anti_target"]:
        draw_polyline(diamond,color,1.7,true)
    elif key in ["normal","anti_normal"]:
        draw_polyline(PackedVector2Array([p+Vector2(-6,5),p+Vector2(0,-6),p+Vector2(6,5)]),color,1.7,true)
    elif key in ["radial_in","radial_out"]:
        draw_line(p+Vector2(-6,-4),p+Vector2(6,4),color,1.7,true)
        draw_line(p+Vector2(-6,4),p+Vector2(6,-4),color,1.7,true)
    elif key=="maneuver_node":
        draw_rect(Rect2(p-Vector2(5,5),Vector2(10,10)),color,false,1.7)
    else:
        draw_arc(p,5,0,TAU,16,color,1.7,true)
        draw_line(p+Vector2(-9,0),p+Vector2(-5,0),color,1.7,true)
        draw_line(p+Vector2(5,0),p+Vector2(9,0),color,1.7,true)
    if key in ["retrograde","anti_normal","radial_in","anti_target"]:
        draw_circle(p,2,color)
