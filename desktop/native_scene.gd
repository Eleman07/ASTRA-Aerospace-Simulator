extends Node3D

const AssetsClass=preload("res://vehicle_assets.gd")
const TerrainClass=preload("res://terrain_stream.gd")
const EffectsClass=preload("res://flight_effects.gd")
var effects=EffectsClass.new()
var assets=AssetsClass.new()
var asset_choice="auto"
var active_asset_id=""
var active_asset={}
var asset_error=""
var camera
var light
var environment
var sky_material
var world_root = Node3D.new()
var vehicle_root = Node3D.new()
var model_root = Node3D.new()
var planet
var ground_root = Node3D.new()
var target_root = Node3D.new()
var plume
var physical_state = {}
var visual = {}
var domain = ""
var model_key = ""
var asset_root = ""
var selected_asset = ""
var catalogue_asset = {}
var last_model_import_ok = false
var azimuth = 0.65
var elevation = 0.25
var distance = 32.0
var base_distance = 32.0
var focus_height = 4.0
var drag = false
var quality = "balanced"
var advanced_renderer = false
var last_sky_center=Vector3.INF
var last_planet_basis=Basis.IDENTITY
var last_atmosphere=-1.0
var traces = []
var trace_mesh
var replay = false
var material_cache = {}
var geometry_cache = {}
var animated_rotors = []
var gear_parts = []
var control_parts = []
var heat_materials = []
var map_root = Node3D.new()
var map_visible = false
var transfer_marker
var launch_site
var launch_root=Node3D.new()
var terrain_material
var texture_cache={}
var deck_height=0.0
var terrain_stream
var pose_from={}
var pose_to={}
var pose_elapsed=0.0
var pose_period=.08
var last_pose_wall=0
var rendered_altitude=0.0
var is_running=false
var frame_time=0.0
var reflection_time=0.0
var cinematic_effects=true
var last_state_time=-1.0
var earthshine_light
var enhanced_materials=true
var earthshine=true

func surface_texture(file):
    if texture_cache.has(file):return texture_cache[file]
    var image=Image.load_from_file(asset_root.path_join(file))
    if image==null or image.is_empty():return null
    image.generate_mipmaps()
    var texture=ImageTexture.create_from_image(image);texture_cache[file]=texture
    return texture

func setup(assets,profile):
    asset_root = assets
    add_child(effects);effects.setup(asset_root)
    self.assets.setup(asset_root,profile)
    quality = profile
    advanced_renderer = RenderingServer.get_current_rendering_method()=="forward_plus"
    var viewport=get_viewport()
    viewport.scaling_3d_mode=Viewport.SCALING_3D_MODE_FSR2 if advanced_renderer and profile=="balanced" else Viewport.SCALING_3D_MODE_BILINEAR
    viewport.scaling_3d_scale=.67 if advanced_renderer and profile=="balanced" else {"low":.65,"balanced":.82,"high":1.0,"ultra":1.15,"cinema":1.5}.get(profile,.82)
    add_child(world_root)
    world_root.add_child(ground_root)
    world_root.add_child(launch_root)
    add_child(vehicle_root)
    vehicle_root.add_child(model_root)
    add_child(target_root)
    add_child(map_root)
    map_root.visible=false
    camera = Camera3D.new()
    camera.near = 0.1
    camera.far = 30000.0
    camera.fov = 48
    camera.attributes=CameraAttributesPractical.new()
    camera.attributes.auto_exposure_min_sensitivity=80
    camera.attributes.auto_exposure_max_sensitivity=400
    camera.attributes.auto_exposure_speed=2.5
    camera.attributes.dof_blur_amount=.08
    add_child(camera)
    camera.current = true
    light = DirectionalLight3D.new()
    light.rotation_degrees = Vector3(-35,-38,0)
    light.light_color = Color(1.0,0.93,0.82)
    light.light_energy = 1.5
    light.shadow_enabled = profile!="low"
    light.directional_shadow_max_distance = 1800
    light.directional_shadow_mode=DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
    light.directional_shadow_blend_splits=true
    add_child(light)
    earthshine_light=DirectionalLight3D.new()
    earthshine_light.light_color=Color(.32,.53,1.0)
    earthshine_light.light_energy=.12 if profile!="low" else 0.0
    earthshine_light.rotation_degrees=Vector3(75,0,0)
    earthshine_light.shadow_enabled=false
    add_child(earthshine_light)
    environment = Environment.new()
    environment.background_mode = Environment.BG_SKY
    environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
    environment.ambient_light_energy = 0.32
    environment.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
    environment.tonemap_mode = Environment.TONE_MAPPER_ACES
    environment.tonemap_exposure = 1.0
    environment.glow_enabled = advanced_renderer
    environment.ssao_enabled = advanced_renderer and profile!="low"
    environment.ssr_enabled = advanced_renderer and profile in ["high","ultra","cinema"]
    environment.ssil_enabled = advanced_renderer and profile in ["ultra","cinema"]
    var sky = Sky.new()
    sky.process_mode=Sky.PROCESS_MODE_INCREMENTAL
    sky.radiance_size=Sky.RADIANCE_SIZE_128
    sky_material = ShaderMaterial.new()
    sky_material.shader = load("res://sky.gdshader")
    sky_material.set_shader_parameter("nebula_steps",0 if profile=="low" else 6 if profile in ["high","ultra","cinema"] else 3)
    sky_material.set_shader_parameter("atmosphere_steps",4 if profile=="low" else 16 if profile in ["high","ultra","cinema"] else 8)
    var suffix="1k" if profile=="low" else "2k"
    var emission=Image.load_from_file(asset_root.path_join("nebula-blue-emission-"+suffix+".exr"))
    var transmission=Image.load_from_file(asset_root.path_join("nebula-blue-transmission-"+suffix+".exr"))
    if emission!=null and transmission!=null and not emission.is_empty() and not transmission.is_empty():
        emission.convert(Image.FORMAT_RGBAH);transmission.convert(Image.FORMAT_RGBAH)
        emission.generate_mipmaps();transmission.generate_mipmaps()
        sky_material.set_shader_parameter("nebula_emission",ImageTexture.create_from_image(emission))
        sky_material.set_shader_parameter("nebula_transmission",ImageTexture.create_from_image(transmission))
        sky_material.set_shader_parameter("use_baked_nebula",true)
    sky.sky_material = sky_material
    environment.sky = sky
    sky_material.set_shader_parameter("sun_direction",light.global_basis.z.normalized())
    get_viewport().use_taa=advanced_renderer and profile in ["high","ultra","cinema"]
    if get_viewport().use_taa or (advanced_renderer and profile=="balanced") or profile=="low":
        get_viewport().msaa_3d=Viewport.MSAA_DISABLED
    elif profile=="balanced":get_viewport().msaa_3d=Viewport.MSAA_2X
    var node = WorldEnvironment.new()
    node.environment = environment
    add_child(node)

func set_quality(profile):
    if profile not in ["low","balanced","high","ultra","cinema","cinema"]:return false
    if profile==quality:return true
    quality=profile
    var use_fsr2=advanced_renderer and profile=="balanced"
    get_viewport().scaling_3d_mode=Viewport.SCALING_3D_MODE_FSR2 if use_fsr2 else Viewport.SCALING_3D_MODE_BILINEAR
    var scale=.67 if use_fsr2 else {"low":.65,"balanced":.82,"high":1.0,"ultra":1.15,"cinema":1.5}[profile]
    get_viewport().scaling_3d_scale=scale
    get_viewport().use_taa=advanced_renderer and profile in ["high","ultra","cinema"]
    get_viewport().msaa_3d=Viewport.MSAA_DISABLED if get_viewport().use_taa or profile=="low" or use_fsr2 else Viewport.MSAA_2X if profile=="balanced" else Viewport.MSAA_4X
    environment.glow_enabled=advanced_renderer and profile!="low"
    environment.ssao_enabled=advanced_renderer and profile!="low"
    environment.ssr_enabled=advanced_renderer and profile in ["high","ultra","cinema"]
    environment.ssil_enabled=advanced_renderer and profile in ["ultra","cinema"]
    environment.sdfgi_enabled=advanced_renderer and profile in ["ultra","cinema"] and domain in ["air","moon"]
    earthshine_light.light_energy=.12 if earthshine and profile!="low" else 0.0
    light.shadow_enabled=profile!="low"
    light.directional_shadow_max_distance=600.0 if profile=="low" else 1200.0 if profile=="balanced" else 2200.0
    sky_material.set_shader_parameter("nebula_steps",0 if profile=="low" else 6 if profile in ["high","ultra","cinema"] else 3)
    sky_material.set_shader_parameter("atmosphere_steps",4 if profile=="low" else 16 if profile in ["high","ultra","cinema"] else 8)
    if map_visible:return true
    build_environment()
    if asset_choice!="custom":selected_asset=assets.choose_file(active_asset,physical_state,profile)
    build_vehicle()
    return true

func mat(color,metal=0.0,rough=0.6):
    var key = str(color)+str(metal)+str(rough)
    if material_cache.has(key):return material_cache[key]
    var material = StandardMaterial3D.new()
    material.albedo_color = color
    material.metallic = metal
    material.roughness = rough
    if metal>0.15 and rough<0.65:
        material.clearcoat_enabled = true
        material.clearcoat = .65
        material.clearcoat_roughness = .18
    material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
    material_cache[key] = material
    return material

func mesh_node(parent,mesh,position,scale_value,material):
    var node = MeshInstance3D.new()
    node.mesh = mesh
    node.position = position
    node.scale = scale_value
    node.material_override = material
    parent.add_child(node)
    return node

func box(parent,position,size,color,metal=0.0,rough=0.6):
    var key="box/"+str(size)
    if not geometry_cache.has(key):
        var mesh=BoxMesh.new();mesh.size=size;geometry_cache[key]=mesh
    return mesh_node(parent,geometry_cache[key],position,Vector3.ONE,mat(color,metal,rough))

func cylinder(parent,position,radius,height,color,metal=0.0,top_radius=-1.0):
    var key="cylinder/"+str(radius)+"/"+str(height)+"/"+str(top_radius)
    if not geometry_cache.has(key):
        var mesh=CylinderMesh.new()
        mesh.bottom_radius=radius;mesh.top_radius=radius if top_radius<0 else top_radius
        mesh.height=height;mesh.radial_segments=48 if quality!="low" else 24
        geometry_cache[key]=mesh
    return mesh_node(parent,geometry_cache[key],position,Vector3.ONE,mat(color,metal,0.35 if metal>0 else 0.7))

func strut(parent,a,b,radius,color):
    var node = cylinder(parent,(a+b)*0.5,radius,a.distance_to(b),color,0.75)
    var axis = (b-a).normalized()
    if absf(axis.y)<0.999:
        var x = Vector3.UP.cross(axis).normalized()
        node.basis = Basis(x,axis,x.cross(axis)).orthonormalized()

func clear_node(node):
    for child in node.get_children():
        node.remove_child(child)
        child.queue_free()

func set_snapshot(snapshot):
    physical_state = snapshot.get("state",{})
    visual = snapshot.get("visual",{})
    effects.update_state(snapshot)
    if map_visible:return
    active_asset_id=assets.automatic(physical_state) if asset_choice=="auto" else asset_choice
    active_asset=assets.models.get(active_asset_id,{"name":"GLB importato","rotation_deg":[0,0,0]})
    if asset_choice!="custom":selected_asset=assets.choose_file(active_asset,physical_state,quality)
    var next_domain = str(visual.get("domain","earth"))
    var key = str(physical_state.get("model_id",""))+":"+str(physical_state.get("scenario",""))+":"+str(physical_state.get("active_stage",0))+":"+selected_asset
    if physical_state.get("phase","") in ["AEROSHELL","DROGUE","PARACHUTE","LANDED"] and domain=="earth":key+="/"+str(physical_state.phase)
    if domain!=next_domain:
        domain = next_domain
        build_environment()
        traces.clear()
    if model_key!=key:
        model_key = key
        build_vehicle()
    var offset = visual.get("ground_offset_m",[0,0,0])
    var launch_offset=visual.get("launch_site_offset_m",[0,0,0])
    launch_root.position=Vector3(float(launch_offset[0]),float(launch_offset[1]),float(launch_offset[2]))
    launch_root.visible=domain=="earth" and launch_root.position.length()<15000
    var next_ground=Vector3(float(offset[0]),float(offset[1]),float(offset[2]))
    if is_instance_valid(planet):
        planet.position = Vector3(0,-float(visual.get("planet_radius_m",6378137))-float(visual.get("altitude_m",0)),0)
        var cols = visual.get("planet_basis",[])
        if cols.size()==3:planet.basis = array_basis(cols)
    var next_basis=Basis.IDENTITY
    if physical_state.get("vehicle")=="space":
        next_basis = array_basis(visual.get("vehicle_basis",[[1,0,0],[0,1,0],[0,0,1]]))
    else:
        var att = physical_state.get("attitude_deg",[0,0,0])
        next_basis = Basis(Vector3.UP,-deg_to_rad(float(att[2])))*Basis(Vector3.RIGHT,deg_to_rad(float(att[1])))*Basis(Vector3.BACK,-deg_to_rad(float(att[0])))
    var wall=Time.get_ticks_msec()
    var simulation_time=float(physical_state.get("time_s",0))
    var external_stream=snapshot.get("desktop",{}).get("clock_owner","")=="external" and simulation_time>last_state_time
    is_running=bool(snapshot.get("desktop",{}).get("running",false)) or external_stream
    last_state_time=simulation_time
    var next_pose={"ground":next_ground,"rotation":next_basis.get_rotation_quaternion(),"altitude":float(visual.get("altitude_m",0)),"launch":launch_root.position}
    var snap_now=pose_to.is_empty() or not is_running or float(physical_state.get("time_s",0))==0 or ground_root.position.distance_to(next_ground)>2000
    pose_from=next_pose if snap_now else {"ground":ground_root.position,"rotation":vehicle_root.basis.get_rotation_quaternion(),"altitude":rendered_altitude,"launch":pose_to.launch}
    pose_to=next_pose
    pose_period=clampf((wall-last_pose_wall)*.001,.03,.16) if last_pose_wall>0 else .08
    last_pose_wall=wall;pose_elapsed=pose_period if snap_now else 0.0
    if snap_now:ground_root.position=next_ground;vehicle_root.basis=next_basis;rendered_altitude=next_pose.altitude
    if is_instance_valid(terrain_stream):terrain_stream.update_center(Vector2(-next_ground.x,-next_ground.z))
    if domain in ["earth","orbit","moon","air"]:
        var planet_basis=array_basis(visual.get("planet_basis",[[1,0,0],[0,1,0],[0,0,1]])).inverse()
        if not planet_basis.is_equal_approx(last_planet_basis):RenderingServer.global_shader_parameter_set("planet_rotation",planet_basis);last_planet_basis=planet_basis
    var target = visual.get("target_offset_m")
    target_root.visible = target!=null
    if target!=null:target_root.position=Vector3(float(target[0]),float(target[1]),float(target[2]))
    if is_instance_valid(plume):
        var force = float(physical_state.get("propulsion",{}).get("applied_thrust_N",0))
        plume.visible = force>1
        plume.scale.y = clampf(sqrt(force/10000.0),0.2,8.0)
        plume.material_override.set_shader_parameter("pressure_ratio",clampf(float(physical_state.get("environment",{}).get("pressure_Pa",0))/101325.0,0,1))
    if physical_state.get("time_s",0)==0:traces.clear()
    var dose = float(physical_state.get("mission_metrics",{}).get("stagnation_point_convective_heat_load_J_m2",0))
    for material in heat_materials:material.set_shader_parameter("heat_dose",dose)
    var surfaces=physical_state.get("control_surfaces",{}).get("actual_deflection_rad",[0,0,0])
    for part in control_parts:
        part.node.rotation.x=float(surfaces[part.axis])*part.sign

func array_basis(columns):
    var c = []
    for v in columns:c.append(Vector3(float(v[0]),float(v[1]),float(v[2])))
    return Basis(c[0],c[1],c[2]).orthonormalized()

func build_environment():
    last_sky_center=Vector3.INF;last_planet_basis=Basis.IDENTITY;last_atmosphere=-1
    RenderingServer.global_shader_parameter_set("planet_rotation",Basis.IDENTITY)
    clear_node(ground_root)
    clear_node(launch_root)
    if is_instance_valid(planet):planet.queue_free()
    planet = null
    sky_material.set_shader_parameter("planet_visible",true)
    var earth_file="earth-natural-8k.webp" if quality in ["high","ultra","cinema"] else "earth-natural-5.4k.webp" if quality=="balanced" else "earth-natural-2k.webp"
    var file="celestial/moon-4k.webp" if domain=="moon" and quality in ["high","ultra","cinema"] else "celestial/moon-2k.webp" if domain=="moon" else earth_file
    var texture=surface_texture(file)
    if texture!=null:sky_material.set_shader_parameter("planet_texture",texture)
    sky_material.set_shader_parameter("lunar_planet",domain=="moon")
    sky_material.set_shader_parameter("planet_radius",1.7374 if domain=="moon" else 6.378137)
    sky_material.set_shader_parameter("companion_visible",domain in ["earth","orbit","moon"])
    sky_material.set_shader_parameter("companion_radius",6.378137 if domain=="moon" else 1.7374)
    var companion_texture=surface_texture(earth_file if domain=="moon" else "celestial/moon-2k.webp")
    if companion_texture!=null:sky_material.set_shader_parameter("companion_texture",companion_texture)
    environment.sdfgi_enabled = advanced_renderer and quality=="ultra" and domain in ["air","moon"]
    if domain in ["air","earth","moon"]:
        make_terrain(domain=="moon")
        if domain=="air":make_airfield()
        elif domain=="earth":make_launch_site()
    clear_node(target_root)
    if domain=="orbit":
        var station=assets.instantiate(asset_root.path_join("vehicles/nasa-iss-b.glb"),assets.models["nasa-iss"],55,-1,true)
        if station!=null:target_root.add_child(station)

func make_terrain(moon):
    # Height sampling lives in the vertex shader; every resident tile shares
    # one of two immutable meshes. No per-tile CPU triangulation during flight.
    var material=ShaderMaterial.new();material.shader=load("res://terrain.gdshader")
    material.set_shader_parameter("lunar",moon);material.set_shader_parameter("streamed",true)
    material.set_shader_parameter("patch_radius",23000.0)
    if not moon:
        var texture=surface_texture("earth-cape-near-4k.webp" if quality in ["high","ultra","cinema"] else "earth-cape-near-2k.webp")
        if texture!=null:material.set_shader_parameter("ground_image",texture);material.set_shader_parameter("use_image",true)
    terrain_material=material
    terrain_stream=TerrainClass.new();ground_root.add_child(terrain_stream);terrain_stream.setup(material,moon)
    var offset=visual.get("ground_offset_m",[0,0,0]);terrain_stream.update_center(Vector2(-float(offset[0]),-float(offset[2])))
    return

func make_airfield():
    box(ground_root,Vector3(0,-.06,-1350),Vector3(30,.12,3000),Color(.075,.085,.105),0,.93)
    for i in range(60):
        box(ground_root,Vector3(0,.015,140-i*50),Vector3(.8,.025,18),Color(.85,.85,.8))
    for side in [-1,1]:
        box(ground_root,Vector3(side*14.3,.012,-1350),Vector3(.16,.025,2980),Color(.85,.85,.81))
        for i in range(34):
            var marker = box(ground_root,Vector3(side*17,.45,140-i*90),Vector3(.3,.4,.3),Color(.55,.72,.95))
            var material = marker.material_override.duplicate()
            material.emission_enabled = true
            material.emission = Color(.18,.4,.8)
            material.emission_energy_multiplier = 2
            marker.material_override = material
    for x in [-110,110]:
        box(ground_root,Vector3(x,7,-240),Vector3(65,14,50),Color(.27,.31,.36),.35)
        box(ground_root,Vector3(x,14.5,-240),Vector3(68,1,53),Color(.16,.2,.25),.5)
        for i in [-1,0,1]:box(ground_root,Vector3(x+i*19,6,-214.5),Vector3(16,11,.1),Color(.09,.18,.24),.55,.22)

func make_launch_site():
    # NASA authored platform, service tower, trusses and umbilicals.
    # Match the physical ASTRA rocket length to the 98 m SLS reference.
    var reference_length=float(visual.get("reference_geometry",{}).get("body_length_m",13))
    var ratio=reference_length/98.0
    deck_height=14.65*ratio
    launch_site=assets.instantiate(asset_root.path_join("vehicles/nasa-mobile-launcher.glb"),{"rotation_deg":[0,0,0]},115.8*ratio,1)
    if launch_site!=null:
        launch_root.add_child(launch_site)
        launch_site.position+=Vector3(14,.35,0)*ratio
    box(launch_root,Vector3(0,-.06,0),Vector3(18,.12,22),Color(.18,.20,.21),0,.95)

func build_vehicle():
    effects.clear_vehicle()
    clear_node(model_root)
    vehicle_root.basis=Basis.IDENTITY
    model_root.scale=Vector3.ONE
    plume=null;last_model_import_ok=false
    animated_rotors.clear();control_parts.clear();heat_materials.clear()
    var kind=str(physical_state.get("vehicle","space"))
    model_root.position=Vector3(0,-1.5,0) if kind=="space" and domain=="earth" else Vector3.ZERO
    base_distance=22 if kind=="aircraft" else 2.5 if kind=="drone" else 14 if domain=="moon" else 19 if domain=="orbit" else 35
    focus_height=1.2 if kind=="aircraft" else .2 if kind=="drone" else 1.7 if domain=="moon" else 0 if domain=="orbit" else 6
    distance=base_distance
    var parameters=physical_state.get("vehicle_parameters",{})
    var recovery=physical_state.get("phase","") in ["AEROSHELL","DROGUE","PARACHUTE","LANDED"]
    var size=13.0
    if kind=="space" and domain=="earth":size=float(parameters.get("body_length_m",13))
    var dimension=1
    if kind=="aircraft":size=float(parameters.get("b_m",10.5));dimension=0
    elif kind=="drone":size=2*(float(parameters.get("arm_m",.23))+float(parameters.get("rotor_radius_m",.127)));dimension=-1
    elif domain=="moon":size=4.8;dimension=-1
    elif domain=="orbit":size=6.5;dimension=-1
    elif recovery and active_asset.has("recovery_file"):
        size=float(active_asset.get("recovery_reference_length_m",3.4));base_distance=18;distance=18;focus_height=1.5
    var instance=assets.instantiate(selected_asset,active_asset,size,dimension,domain=="orbit")
    if instance==null:
        asset_error=assets.last_error
        return
    asset_error="";last_model_import_ok=true
    model_root.add_child(instance)
    if enhanced_materials and quality!="low":assets.add_surface_detail(instance)
    effects.build(model_root,assets.get_bounds(instance),kind,domain=="orbit")
    for node in instance.find_children("*","Node3D",true,false):
        if node.name.begins_with("Rotor_") or node.name.begins_with("Propeller_"):
            var is_rotor=node.name.begins_with("Rotor_")
            var index=int(str(node.name).get_slice("_",1))
            animated_rotors.append({"node":node,"axis":"y" if is_rotor else str(active_asset.get("animation_axis","x")),"kind":"rotor" if is_rotor else "propeller","index":index})
            effects.add_rotor_disc(node,"y" if is_rotor else str(active_asset.get("animation_axis","x")))
    if physical_state.get("phase","") in ["DROGUE","PARACHUTE"]:make_recovery_effects()

func make_recovery_effects():
    var area=float(visual.get("reference_geometry",{}).get("parachute_area_m2",160))
    var radius=sqrt(area/PI) if physical_state.get("phase")=="PARACHUTE" else 2.0
    var canopy=SphereMesh.new();canopy.radius=radius;canopy.height=radius*2;canopy.is_hemisphere=true;canopy.radial_segments=48;canopy.rings=24
    var cloth=mat(Color(.82,.7,.42),0,.94).duplicate();cloth.cull_mode=BaseMaterial3D.CULL_DISABLED
    mesh_node(model_root,canopy,Vector3(0,15,0),Vector3(1,.55,1),cloth)
    for i in range(20):
        var angle=i*TAU/20
        strut(model_root,Vector3(cos(angle)*1.2,2.4,sin(angle)*1.2),Vector3(cos(angle)*radius,15,sin(angle)*radius),.012,Color(.7,.71,.65))
    focus_height=7;distance=42

func _exit_tree():assets.clear()

func make_plume(y,radius):
    var mesh = CylinderMesh.new()
    mesh.top_radius = radius
    mesh.bottom_radius = radius*2
    mesh.height = 3.0
    var material = ShaderMaterial.new()
    material.shader = load("res://plume.gdshader")
    plume = mesh_node(model_root,mesh,Vector3(0,y-1.5,0),Vector3.ONE,material)
    plume.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    plume.visible = false

func _process(dt):
    if camera==null:return
    frame_time+=dt
    reflection_time+=dt
    if reflection_time>.25:
        reflection_time=0.0;sky_material.set_shader_parameter("reflection_refresh",frame_time)
    if not pose_to.is_empty():
        pose_elapsed+=dt
        var alpha=clampf(pose_elapsed/maxf(.001,pose_period),0,1)
        ground_root.position=pose_from.ground.lerp(pose_to.ground,alpha)
        launch_root.position=pose_from.launch.lerp(pose_to.launch,alpha)
        vehicle_root.basis=Basis(pose_from.rotation.slerp(pose_to.rotation,alpha))
        rendered_altitude=lerpf(pose_from.altitude,pose_to.altitude,alpha)
    camera.attributes.dof_blur_far_distance=distance*1.35
    camera.attributes.dof_blur_far_transition=distance*1.1
    camera.attributes.dof_blur_near_distance=distance*.5
    camera.attributes.dof_blur_near_transition=maxf(.2,distance*.2)
    if map_visible:
        var map_pos=Vector3(sin(azimuth)*cos(elevation),sin(elevation),cos(azimuth)*cos(elevation))*distance
        camera.position=camera.position.lerp(map_pos,1.0-exp(-dt*6))
        camera.look_at(Vector3.ZERO,Vector3.UP)
        return
    for rotor in animated_rotors:
        if not is_instance_valid(rotor.node):continue
        var rate=0.0
        if rotor.kind=="rotor":
            var phase=physical_state.get("propulsion_actuators",{}).get("rotor_phase_rad",[])
            if int(rotor.index)<phase.size():rotor.node.rotation.y=float(phase[int(rotor.index)])
        else:
            var power=float(physical_state.get("propulsion",{}).get("actual_power_pct",0))/100
            rate=lerpf(0.0,2700.0,sqrt(power))*TAU/60
            rotor.node.rotate_object_local(Vector3.RIGHT if rotor.axis=="x" else Vector3.UP,rate*dt)
    var target = Vector3(0,focus_height,0)
    var pos = target+Vector3(sin(azimuth)*cos(elevation),sin(elevation),cos(azimuth)*cos(elevation))*distance
    if domain=="earth" and physical_state.get("phase","") not in ["AEROSHELL","DROGUE","PARACHUTE","LANDED"]:
        model_root.position.y=-1.5+deck_height*(1.0-smoothstep(100.0,500.0,float(visual.get("altitude_m",0))))
    camera.position = camera.position.lerp(pos,1.0-exp(-dt*14))
    # Keep the inspection camera above the body; sky spheres use camera-relative
    # megametres, independent of the local mesh far clipping plane.
    var radius=float(visual.get("planet_radius_m",6378137))
    var center=Vector3(0,-radius-rendered_altitude,0)
    var radial=camera.position-center
    if radial.length()<radius+2:camera.position=center+radial.normalized()*(radius+2)
    camera.look_at(target,Vector3.UP)
    if cinematic_effects and is_running:
        var vibration=clampf(float(physical_state.get("propulsion",{}).get("applied_thrust_N",0))/320000.,0,1)*.007
        camera.position+=camera.basis.x*sin(frame_time*53.)*vibration+camera.basis.y*sin(frame_time*67.)*vibration*.6
    var heat=float(physical_state.get("environment",{}).get("stagnation_point_convective_heat_flux_W_m2",0))
    effects.cinematic=cinematic_effects
    effects.reentry_heat=heat
    var camera_altitude=maxf(0,(camera.position-center).length()-radius)
    var atmo=0.0 if domain=="moon" else clampf(1.0-camera_altitude/80000.0,0,1)
    if absf(atmo-last_atmosphere)>.002:RenderingServer.global_shader_parameter_set("atmosphere",atmo);last_atmosphere=atmo
    environment.ambient_light_energy=.1 if domain=="moon" else lerpf(.035,.35,atmo)
    var sky_center=(center-camera.position)*.000001
    if sky_center!=last_sky_center:RenderingServer.global_shader_parameter_set("planet_center",sky_center);last_sky_center=sky_center
    if visual.has("companion_center_Mm"):
        var other=visual.companion_center_Mm
        RenderingServer.global_shader_parameter_set("companion_center",Vector3(float(other[0]),float(other[1]),float(other[2]))-camera.position*.000001)

    var local_view=1.0-smoothstep(30000.0,80000.0,maxf(camera_altitude,distance*.25))
    ground_root.visible=local_view>.001
    if is_instance_valid(terrain_material):
        terrain_material.set_shader_parameter("patch_visibility",local_view)
        terrain_material.set_shader_parameter("stream_center",Vector2(-ground_root.position.x,-ground_root.position.z))

func show_solar_map(catalogue):
    clear_node(map_root)
    map_visible=true;map_root.visible=true;world_root.visible=false;vehicle_root.visible=false;target_root.visible=false
    distance=1000;elevation=.35
    RenderingServer.global_shader_parameter_set("atmosphere",0.0)
    sky_material.set_shader_parameter("planet_visible",false)
    sky_material.set_shader_parameter("companion_visible",false)
    for body in catalogue.get("objects",[]):
        if body.get("class","")=="moon":continue
        var position=body.get("position_heliocentric_m",[0,0,0])
        var center=Vector3(float(position[0]),float(position[2]),-float(position[1]))/149597870700.0*20
        var radius=2.5 if body.id=="sun" else maxf(.7,minf(2.0,float(body.get("radius_m",1))/6378137.0*.7))
        var sphere=SphereMesh.new();sphere.radius=radius;sphere.height=radius*2;sphere.radial_segments=48;sphere.rings=24
        var material=mat(Color(body.get("color","#a8b9ce")),0,.7).duplicate()
        var file="earth-natural-2k.webp" if body.id=="earth" else "celestial/venus_atmosphere-2k.webp" if body.id=="venus" else "celestial/"+str(body.id)+"-2k.webp"
        var texture=surface_texture(file)
        if texture!=null:material.albedo_color=Color.WHITE;material.albedo_texture=texture
        if body.id=="sun":material.emission_enabled=true;material.emission=Color(1,.65,.22);material.emission_energy_multiplier=3
        mesh_node(map_root,sphere,center,Vector3.ONE,material)
        var label=Label3D.new();label.text=str(body.get("name",body.id));label.font_size=28;label.pixel_size=.07;label.position=center+Vector3(0,4,0);label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;map_root.add_child(label)
        var orbital_radius=float(body.get("semi_major_axis_m",0))/149597870700.0*20
        if orbital_radius>0:
            var points=[]
            for i in range(181):
                var angle=i*TAU/180
                points.append(Vector3(cos(angle)*orbital_radius,0,sin(angle)*orbital_radius))
            line_strip(map_root,points,Color(.13,.25,.38))

func inspect_body(catalogue,body_id):
    # Inspection separates the body's true surface from the illustrative map
    # scale. Earth/Moon radii and separation retain their physical ratio.
    clear_node(map_root)
    map_visible=true;map_root.visible=true;world_root.visible=false;vehicle_root.visible=false;target_root.visible=false
    RenderingServer.global_shader_parameter_set("atmosphere",0.0);sky_material.set_shader_parameter("planet_visible",false)
    sky_material.set_shader_parameter("companion_visible",false)
    distance=320;elevation=.2
    for body in catalogue.get("objects",[]):
        if body.id!=body_id:continue
        var sphere=SphereMesh.new();sphere.radius=100;sphere.height=200;sphere.radial_segments=128 if quality!="low" else 64;sphere.rings=64 if quality!="low" else 32
        var material=mat(Color.WHITE,0,.94).duplicate()
        var file="earth-natural-8k.webp" if body_id=="earth" and quality in ["high","ultra","cinema"] else "earth-natural-5.4k.webp" if body_id=="earth" and quality=="balanced" else "earth-natural-2k.webp" if body_id=="earth" else "celestial/moon-4k.webp" if body_id=="moon" and quality in ["high","ultra","cinema"] else "celestial/moon-2k.webp" if body_id=="moon" else "celestial/venus_atmosphere-2k.webp" if body_id=="venus" else "celestial/"+body_id+"-2k.webp"
        var texture=surface_texture(file)
        if texture!=null:material.albedo_texture=texture
        else:material.albedo_color=Color(body.get("color","#a8b9ce"))
        mesh_node(map_root,sphere,Vector3.ZERO,Vector3.ONE,material)
        var label=Label3D.new();label.text=str(body.name)+" · R = "+str(float(body.radius_m)/1000)+" km";label.font_size=36;label.pixel_size=.1;label.position=Vector3(0,120,0);label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;map_root.add_child(label)
    camera.position=Vector3(0,160,310)

func line_strip(parent,points,color):
    if points.size()<2:return
    var mesh=ImmediateMesh.new()
    mesh.surface_begin(Mesh.PRIMITIVE_LINE_STRIP)
    for point in points:mesh.surface_add_vertex(point)
    mesh.surface_end()
    var material=mat(color).duplicate();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
    mesh_node(parent,mesh,Vector3.ZERO,Vector3.ONE,material)

func hide_solar_map():
    map_visible=false;map_root.visible=false;world_root.visible=true;vehicle_root.visible=true
    model_key="";domain=""

func show_transfer_state(result):
    var p=result.get("position_m",result.get("position_heliocentric_m",null))
    if p==null:return
    if not is_instance_valid(transfer_marker):
        var sphere=SphereMesh.new();sphere.radius=.9;sphere.height=1.8
        transfer_marker=mesh_node(map_root,sphere,Vector3.ZERO,Vector3.ONE,mat(Color(.2,.7,1),.2,.4))
    transfer_marker.position=Vector3(float(p[0]),float(p[2]),-float(p[1]))/149597870700.0*20

func _unhandled_input(event):
    if event is InputEventMouseButton:
        if event.button_index==MOUSE_BUTTON_RIGHT:drag=event.pressed
        if event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_UP:distance=maxf(.5,distance*.88)
        if event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_DOWN:distance=minf(50000000,distance*1.14)
    if event is InputEventMouseMotion and drag:
        azimuth -= event.relative.x*.005
        elevation = clampf(elevation+event.relative.y*.004,-.8,1.35)
