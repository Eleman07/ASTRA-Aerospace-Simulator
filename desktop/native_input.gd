extends RefCounted

var armed = false
var neutral_acquired = false
var primary = -1
var throttle_device = -1
var pedals_device = -1
var calibration_active = false
var vehicle = "space"
var throttle = 0.0
var target = Vector3.ZERO
var smooth_axes = Vector3.ZERO
var previous_buttons = {}
var pickup = false
var previous_collective = 0.0
const DEFAULT_CONFIG = {"deadzone":0.08,"expo":0.10,"curve":"linear","smoothing_s":0.012,"invert_pitch":false,
    "sensitivity":1.8,"throttle_rate_pct_s":140.0,"orbital_slew_deg_s":90.0,
    "roll_axis":0,"pitch_axis":1,"yaw_axis":2,"throttle_axis":3,"sas_toggle_button":10,"sas_next_button":8,
    "centers":[0.0,0.0,0.0],"minimums":[-1.0,-1.0,-1.0],"maximums":[1.0,1.0,1.0],"profile":"Xbox / standard"}
var config = DEFAULT_CONFIG.duplicate(true)
var calibration_min = []
var calibration_max = []

func _init():
    load_profile("space")

func load_profile(kind):
    vehicle = kind
    config = DEFAULT_CONFIG.duplicate(true)
    var file = ConfigFile.new()
    if file.load("user://controller-profiles.cfg") == OK:
        var data={}
        for key in config:
            data[key] = file.get_value(kind,key,config[key])
        apply_profile(data)
    disarm()

func apply_profile(data):
    if not (data is Dictionary):return false
    var next=config.duplicate(true)
    for key in data:
        if next.has(key):next[key]=data[key]
    for key in ["deadzone","expo","smoothing_s","sensitivity","throttle_rate_pct_s","orbital_slew_deg_s","roll_axis","pitch_axis","yaw_axis","throttle_axis"]:
        if not (next[key] is float or next[key] is int) or not is_finite(float(next[key])):return false
    if float(next.deadzone)<0 or float(next.deadzone)>.45 or float(next.expo)<0 or float(next.expo)>1:return false
    if float(next.smoothing_s)<.001 or float(next.smoothing_s)>.5:return false
    if float(next.sensitivity)<.25 or float(next.sensitivity)>2.5:return false
    if float(next.throttle_rate_pct_s)<10 or float(next.throttle_rate_pct_s)>400:return false
    if float(next.orbital_slew_deg_s)<5 or float(next.orbital_slew_deg_s)>180:return false
    for key in ["sas_toggle_button","sas_next_button"]:
        if not (next[key] is float or next[key] is int):return false
        if not is_finite(float(next[key])) or float(next[key])!=floorf(float(next[key])):return false
        if int(next[key]) < -1 or int(next[key])>20:return false
        # Preserve menu navigation, arming, pause, GNC, and brakes bindings.
        if int(next[key]) in [0,1,2,3,6,9,11,12,13,14]:return false
        next[key]=int(next[key])
    if next.sas_toggle_button>=0 and next.sas_toggle_button==next.sas_next_button:return false
    for key in ["roll_axis","pitch_axis","yaw_axis","throttle_axis"]:
        if float(next[key])!=floorf(float(next[key])) or int(next[key])<0 or int(next[key])>15:return false
        next[key]=int(next[key])
    if not (next.invert_pitch is bool) or not (next.profile is String) or not (next.curve is String):return false
    if next.curve not in ["linear","exponential"]:return false
    for key in ["centers","minimums","maximums"]:
        if not (next[key] is Array) or next[key].size()!=3:return false
        for item in next[key]:
            if not (item is float or item is int) or not is_finite(float(item)) or absf(float(item))>1:return false
    for i in range(3):
        if float(next.minimums[i])>float(next.centers[i]) or float(next.maximums[i])<float(next.centers[i]):return false
    disarm()
    config=next
    return true

func save_profile():
    var file = ConfigFile.new()
    file.load("user://controller-profiles.cfg")
    for key in config:
        file.set_value(vehicle,key,config[key])
    file.save("user://controller-profiles.cfg")

func disarm():
    armed = false
    neutral_acquired = false
    calibration_active = false
    smooth_axes = Vector3.ZERO
    pickup = false

func assign_device(slot,id):
    if slot not in ["primary","throttle_device","pedals_device"]:return false
    if slot!="primary" and id>=0:
        for other in ["primary","throttle_device","pedals_device"]:
            if other!=slot and id==get(other):return false
    disarm()
    set(slot,id)
    if slot=="primary" and id>=0:
        if throttle_device==id:throttle_device=-1
        if pedals_device==id:pedals_device=-1
    return true

func response(value, center = 0.0):
    value = clampf(value-center,-1.0,1.0)
    var zone = clampf(float(config.deadzone),0.0,0.45)
    var normalized = maxf(0.0,(absf(value)-zone)/(1.0-zone))
    var curved = pow(normalized,2.0) if config.curve=="exponential" else normalized
    curved = lerpf(curved,pow(normalized,3.0),float(config.expo))
    return signf(value)*clampf(curved*float(config.sensitivity),0.0,1.0)

func calibrated_response(raw,index):
    var center=float(config.centers[index])
    var lows=config.get("minimums",[-1.0,-1.0,-1.0])
    var highs=config.get("maximums",[1.0,1.0,1.0])
    var range_value=maxf(.05,float(highs[index])-center) if raw>=center else maxf(.05,center-float(lows[index]))
    return response((raw-center)/range_value)

func start_calibration():
    calibrate()
    if primary not in Input.get_connected_joypads():return false
    calibration_min=config.centers.duplicate()
    calibration_max=config.centers.duplicate()
    calibration_active=true
    return true

func capture_calibration():
    if not calibration_active:return
    var mappings=[config.roll_axis,config.pitch_axis,config.yaw_axis]
    for i in range(3):
        var value=Input.get_joy_axis(primary,int(mappings[i]))
        calibration_min[i]=minf(calibration_min[i],value)
        calibration_max[i]=maxf(calibration_max[i],value)

func finish_calibration():
    if calibration_active:
        for i in range(3):
            if calibration_max[i]-calibration_min[i]<.5:
                calibration_min[i]=-1.0;calibration_max[i]=1.0
        config.minimums=calibration_min.duplicate()
        config.maximums=calibration_max.duplicate()
        save_profile()
    calibration_active=false

func calibrate():
    disarm()
    calibration_active = true
    if primary in Input.get_connected_joypads():
        config.centers = [Input.get_joy_axis(primary,int(config.roll_axis)),
            Input.get_joy_axis(primary,int(config.pitch_axis)),Input.get_joy_axis(primary,int(config.yaw_axis))]
        save_profile()
    calibration_active = false

func raw_axes():
    if primary not in Input.get_connected_joypads():
        return Vector3.ZERO
    var centers = config.centers
    var axes = Vector3(calibrated_response(Input.get_joy_axis(primary,int(config.roll_axis)),0),
        calibrated_response(Input.get_joy_axis(primary,int(config.pitch_axis)),1),
        calibrated_response(Input.get_joy_axis(primary,int(config.yaw_axis)),2))
    if pedals_device in Input.get_connected_joypads():
        axes.z = response(Input.get_joy_axis(pedals_device,0))
    if bool(config.invert_pitch):
        axes.y *= -1.0
    return axes

func arm(state):
    if calibration_active or primary not in Input.get_connected_joypads() or raw_axes().length() > 0.12:
        return false
    neutral_acquired = true
    armed = true
    throttle = float(state.get("command",{}).get("throttle_pct",0))
    var angles = state.get("attitude_target_deg",[0,0,0])
    target = Vector3(float(angles[0]),float(angles[1]),float(angles[2]))
    smooth_axes = Vector3.ZERO
    pickup = throttle_device < 0
    return true

func pressed(button):
    return primary in Input.get_connected_joypads() and Input.is_joy_button_pressed(primary,button)

func rising(button):
    var value = pressed(button)
    var old = bool(previous_buttons.get(button,false))
    previous_buttons[button] = value
    return value and not old

func sample(dt,state):
    if not armed:
        return {}
    var devices = Input.get_connected_joypads()
    # A gamepad cannot also be a separate throttle or pedal set: this would
    # silently replace RT/LT with its centred right stick (50% throttle).
    if throttle_device==primary:throttle_device=-1
    if pedals_device==primary:pedals_device=-1
    if primary not in devices or (throttle_device >= 0 and throttle_device not in devices) or (pedals_device >= 0 and pedals_device not in devices):
        disarm()
        return {"disconnected":true}
    var absolute=null
    if throttle_device>=0:absolute=clampf((1.0-Input.get_joy_axis(throttle_device,int(config.throttle_axis)))*50.0,0.0,100.0)
    return advance(dt,state,raw_axes(),maxf(0.0,Input.get_joy_axis(primary,JOY_AXIS_TRIGGER_RIGHT)),
        maxf(0.0,Input.get_joy_axis(primary,JOY_AXIS_TRIGGER_LEFT)),pressed(JOY_BUTTON_LEFT_SHOULDER),absolute)

func advance(dt,state,axes,up,down,brakes,absolute=null):
    # Called on every rendered frame, independent of HTTP availability. Only
    # the latest composed command is sent; slow replies never discard time.
    var alpha = 1.0-exp(-dt/maxf(float(config.smoothing_s),0.001))
    smooth_axes = smooth_axes.lerp(axes,alpha)
    if absolute!=null:
        if absf(absolute-throttle)<4 or (absolute-throttle)*(previous_collective-throttle)<0:
            pickup = true
        if pickup:
            throttle = absolute
        previous_collective = absolute
    else:
        throttle = clampf(throttle+(up-down)*float(config.throttle_rate_pct_s)*dt,0.0,100.0)
    var roll_limit = 35.0 if vehicle=="aircraft" else 30.0
    var pitch_limit = 18.0 if vehicle=="aircraft" else 30.0
    var command = {"mode":"manual","throttle_pct":throttle,"roll_deg":smooth_axes.x*roll_limit,
        "pitch_deg":-smooth_axes.y*pitch_limit,"yaw_deg":smooth_axes.z*30.0,
        "brakes_pct":100.0 if brakes else 0.0}
    if state.get("scenario")=="orbital":
        command.attitude_torque_body_fraction = [smooth_axes.x,-smooth_axes.y,smooth_axes.z]
    if vehicle=="space" and state.get("scenario") not in ["orbital","planetary"]:
        command.pitch_deg = clampf(90.0+smooth_axes.y*45.0,-45,90)
    return command
