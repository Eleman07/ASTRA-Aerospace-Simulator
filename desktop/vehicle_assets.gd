extends RefCounted

var root_path=""
var models={}
var defaults={}
var cache={}
var cache_order=[]
var max_cached=4
var loads=0
var cache_hits=0
var last_error=""

func material_key(value):
    return str(value).to_lower().replace(" ","").replace("_","").replace("·","").replace("-","")

func strip_print_stand(arrays):
    var vertices=arrays[Mesh.ARRAY_VERTEX];var indices=arrays[Mesh.ARRAY_INDEX]
    var kept=PackedInt32Array();var removed=0
    for i in range(0,indices.size(),3):
        var support=true
        for k in range(3):
            var p=vertices[indices[i+k]]
            if not (absf(p.x)>19.0 and absf(p.z)>9.0 and p.y<5.2):support=false;break
        if support:removed+=1
        else:kept.append_array(PackedInt32Array([indices[i],indices[i+1],indices[i+2]]))
    if removed==0:return {"arrays":arrays,"removed":0}
    var remap={};var used=[];var compact=PackedInt32Array()
    for old in kept:
        if not remap.has(old):remap[old]=used.size();used.append(old)
        compact.append(remap[old])
    var result=arrays.duplicate()
    for channel in range(Mesh.ARRAY_MAX):
        if channel==Mesh.ARRAY_INDEX or arrays[channel]==null:continue
        var source=arrays[channel]
        if source.size()==0:continue
        var stride=int(source.size()/vertices.size());var subset=source.duplicate();subset.resize(used.size()*stride)
        for i in range(used.size()):
            for k in range(stride):subset[i*stride+k]=source[used[i]*stride+k]
        result[channel]=subset
    result[Mesh.ARRAY_INDEX]=compact
    return {"arrays":result,"removed":removed}

func setup(path,quality):
    root_path=path
    max_cached=2 if quality=="low" else 4
    var catalogue=JSON.parse_string(FileAccess.get_file_as_string("res://vehicles.json"))
    defaults=catalogue.defaults
    for record in catalogue.models:models[record.id]=record

func automatic(state):
    return str(defaults.get(str(state.get("model_id","")),"nasa-insight" if state.get("scenario")=="planetary" else "nasa-sls-block1" if state.get("vehicle")=="space" else "innerscene-twin-turboprop" if state.get("vehicle")=="aircraft" else "innerscene-quadcopter"))

func choose_file(record,state,quality):
    var file=str(record.get("high_file",record.file)) if quality in ["high","ultra","cinema"] else str(record.file)
    if state.get("scenario")=="orbital":file=str(record.get("orbit_file",file))
    elif int(state.get("active_stage",1))>1:file=str(record.get("stage_file",file))
    if state.get("phase","") in ["AEROSHELL","DROGUE","PARACHUTE","LANDED"]:file=str(record.get("recovery_file",file))
    if state.get("phase")=="LANDED":file=str(record.get("landed_file",file))
    return root_path.path_join(file)

func get_bounds(node,transform=Transform3D.IDENTITY):
    var result=AABB()
    var combined=transform*node.transform if node is Node3D else transform
    if node is MeshInstance3D and node.mesh!=null:result=combined*node.get_aabb()
    for child in node.get_children():
        var box=get_bounds(child,combined)
        if box.size.length_squared()>0:result=box if result.size.length_squared()==0 else result.merge(box)
    return result

func sanitize(instance,path,record):
    var omitted=record.get("omit_materials_by_file",{}).get(path.get_file(),record.get("omit_materials",[]))
    var omitted_keys=[]
    for name in omitted:omitted_keys.append(material_key(name))
    var remove_stand=bool(record.get("remove_print_stand",false)) and path.get_file() in ["sls-block1.glb","sls-block1-high.glb"]
    var removed_triangles=0
    if not omitted.is_empty() or remove_stand:
        for node in instance.find_children("*","MeshInstance3D",true,false):
            if node.mesh==null:continue
            var filtered=ArrayMesh.new()
            for i in range(node.mesh.get_surface_count()):
                var material=node.mesh.surface_get_material(i)
                if material!=null and material_key(material.resource_name) in omitted_keys:continue
                var arrays=node.mesh.surface_get_arrays(i)
                if remove_stand and material!=null and "enginebellsandbasehardware" in material_key(material.resource_name):
                    var cleaned=strip_print_stand(arrays);arrays=cleaned.arrays;removed_triangles+=int(cleaned.removed)
                filtered.add_surface_from_arrays(node.mesh.surface_get_primitive_type(i),arrays)
                filtered.surface_set_material(filtered.get_surface_count()-1,material)
            node.mesh=filtered
    instance.set_meta("removed_print_stand_triangles",removed_triangles)

func instantiate(path,record,size,dimension=1,center=false):
    last_error=""
    if not cache.has(path):
        var document=GLTFDocument.new();var state=GLTFState.new()
        if document.append_from_file(path,state)!=OK:
            last_error="Impossibile caricare il modello: "+path.get_file();return null
        var original=document.generate_scene(state)
        if original==null:last_error="Geometria GLB non valida";return null
        sanitize(original,path,record)
        cache[path]=original;cache_order.append(path);loads+=1
        while cache_order.size()>max_cached:
            var oldest=cache_order.pop_front();cache[oldest].free();cache.erase(oldest)
    else:
        cache_hits+=1;cache_order.erase(path);cache_order.append(path)
    var instance=cache[path].duplicate(0)
    var angle=record.get("file_rotations",{}).get(path.get_file(),record.get("rotation_deg",[0,0,0]))
    instance.rotation_degrees=Vector3(float(angle[0]),float(angle[1]),float(angle[2]))
    var box=get_bounds(instance)
    var extent=maxf(box.size.x,maxf(box.size.y,box.size.z)) if dimension<0 else box.size[dimension]
    if extent<=.000001:
        instance.free();last_error="Dimensioni GLB non valide";return null
    instance.scale*=float(size)/extent
    box=get_bounds(instance)
    instance.position-=box.get_center() if center else Vector3(box.get_center().x,box.position.y,box.get_center().z)
    # Preserve authored materials. Only old STL-derived files need two-sided
    # rendering; arbitrary glass and PBR surfaces keep their original settings.
    if record.get("orientation","")=="z":
        for mesh in instance.find_children("*","MeshInstance3D",true,false):
            for i in range(mesh.mesh.get_surface_count()):
                var source=mesh.get_active_material(i)
                if source is BaseMaterial3D:
                    var material=source.duplicate();material.cull_mode=BaseMaterial3D.CULL_DISABLED
                    mesh.set_surface_override_material(i,material)
    return instance

func clear():
    for node in cache.values():node.free()
    cache.clear();cache_order.clear()

var detail_normal
func add_surface_detail(instance):
    # Original tileable micro-panels, rivets and brushed finish. Preserve authored
    # color, metallic, AO, normal, alpha and emission maps; only add absent normals.
    if detail_normal==null:
        var image=Image.create(256,256,false,Image.FORMAT_RGB8)
        for y in range(256):
            for x in range(256):
                var seam_x=1.0 if x%64==0 else -1.0 if x%64==2 else 0.0
                var seam_y=1.0 if y%64==0 else -1.0 if y%64==2 else 0.0
                var rivet=Vector2(float(x%64)-7,float(y%64)-7)
                var radial=rivet.normalized()*.13 if rivet.length()<2.5 else Vector2.ZERO
                var brush=sin(float(y)*2.7+float(x)*.13)*.018
                image.set_pixel(x,y,Color(.5+seam_x*.12+radial.x,.5+seam_y*.12+radial.y+brush,1))
        image.generate_mipmaps();detail_normal=ImageTexture.create_from_image(image)
    for node in instance.find_children("*","MeshInstance3D",true,false):
        node.gi_mode=GeometryInstance3D.GI_MODE_STATIC
        for index in range(node.mesh.get_surface_count()):
            var source=node.get_active_material(index)
            if not source is StandardMaterial3D:continue
            var material=source.duplicate()
            material.texture_filter=BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
            if material.transparency==BaseMaterial3D.TRANSPARENCY_DISABLED:
                if not material.normal_enabled:
                    material.normal_enabled=true;material.normal_texture=detail_normal;material.normal_scale=.28
                    if material.albedo_texture==null:
                        material.uv1_triplanar=true;material.uv1_scale=Vector3(2,2,2)
                if material.metallic>.25:
                    material.clearcoat_enabled=true;material.clearcoat=.22;material.clearcoat_roughness=.3
            node.set_surface_override_material(index,material)
