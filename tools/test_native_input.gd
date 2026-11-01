extends SceneTree

const NativeInput=preload("res://native_input.gd")

func _initialize():
    var pilot=NativeInput.new()
    pilot.disarm()
    assert(not pilot.armed and not pilot.calibration_active)
    assert(pilot.response(.05)==0.0)
    assert(is_equal_approx(pilot.response(1.0),1.0))
    assert(is_equal_approx(pilot.response(-1.0),-1.0))
    assert(pilot.response(.5)>0.0 and pilot.response(.5)<1.0)
    var original=pilot.config.duplicate(true)
    assert(not pilot.apply_profile({"roll_axis":2.5}))
    assert(not pilot.apply_profile({"expo":NAN}))
    assert(not pilot.apply_profile({"centers":[0]}))
    assert(not pilot.apply_profile({"minimums":[.5,-1,-1]}))
    assert(not pilot.apply_profile({"invert_pitch":"false"}))
    assert(not pilot.apply_profile({"sensitivity":0}))
    assert(not pilot.apply_profile({"throttle_rate_pct_s":INF}))
    assert(not pilot.apply_profile({"orbital_slew_deg_s":1000}))
    assert(not pilot.apply_profile({"sas_toggle_button":0}))
    assert(not pilot.apply_profile({"sas_toggle_button":10.5}))
    assert(not pilot.apply_profile({"sas_toggle_button":8,"sas_next_button":8}))
    assert(pilot.config==original)
    assert(pilot.apply_profile({"centers":[.1,-.05,0],"minimums":[-.8,-.9,-1],"maximums":[.9,.85,1]}))
    assert(pilot.calibrated_response(.1,0)==0.0)
    assert(is_equal_approx(pilot.calibrated_response(.9,0),1.0))
    assert(is_equal_approx(pilot.calibrated_response(-.8,0),-1.0))
    pilot.primary=-1
    assert(not pilot.arm({}))
    assert(pilot.sample(.04,{}).is_empty())
    pilot.armed=true
    assert(pilot.sample(.04,{}).get("disconnected",false))
    assert(not pilot.armed)
    pilot.calibrate()
    assert(not pilot.calibration_active)
    assert(not pilot.start_calibration())
    assert(pilot.assign_device("primary",0))
    assert(not pilot.assign_device("throttle_device",0))
    assert(not pilot.assign_device("pedals_device",0))
    assert(pilot.throttle_device==-1 and pilot.pedals_device==-1)
    assert(pilot.assign_device("throttle_device",1))
    assert(not pilot.assign_device("pedals_device",1))
    assert(pilot.assign_device("primary",1))
    assert(pilot.throttle_device==-1)
    assert(not pilot.assign_device("unknown",0))
    assert(pilot.apply_profile(NativeInput.DEFAULT_CONFIG.duplicate(true)))
    # Input integration must not depend on HTTP completion or display rate.
    for frame_dt in [.005,.016,.04,.1]:
        pilot.throttle=0;pilot.smooth_axes=Vector3.ZERO
        var t=0.0
        var command={}
        while t<.8-1e-6:
            var step=minf(frame_dt,.8-t)
            command=pilot.advance(step,{},Vector3(1,-1,1),1,0,false)
            t+=step
        assert(is_equal_approx(command.throttle_pct,100.0))
        assert(command.roll_deg>29.9 and command.pitch_deg>29.9 and command.yaw_deg>29.9)
        command=pilot.advance(.4,{},Vector3.ZERO,0,0,true)
        assert(is_equal_approx(command.throttle_pct,100.0) and command.brakes_pct==100.0)
        command=pilot.advance(.8,{},Vector3.ZERO,0,1,false)
        assert(is_zero_approx(command.throttle_pct))
    pilot.target=Vector3.ZERO;pilot.smooth_axes=Vector3.ZERO
    var orbital={}
    for i in range(60):orbital=pilot.advance(1.0/60.0,{"scenario":"orbital"},Vector3.RIGHT,0,0,false)
    assert(orbital.attitude_torque_body_fraction[0]>.99)
    pilot.smooth_axes=Vector3.ZERO
    var immediate=pilot.advance(.04,{},Vector3.RIGHT,0,0,false)
    assert(immediate.roll_deg>28.9)
    print("NATIVE INPUT PASS: deadzone, expo, endpoints, asymmetric calibration, atomic validation, neutral arm, disconnect and calibration lifecycle")
    print("RESPONSIVENESS PASS: 0-100% in 0.8s at 10/25/62.5/200fps, direct orbital torque, retained throttle, distinct devices")
    quit()
