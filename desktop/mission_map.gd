extends Control
## Local N/E route aid; this control never advances objectives or guidance.
var route=[]
var position_m=Vector2.ZERO
var target_m=Vector2.ZERO
var extent=50.0

func _init():
    custom_minimum_size=Vector2(220,166)
    mouse_filter=Control.MOUSE_FILTER_IGNORE

func set_flight(mission,state,progress):
    route=mission.get("setup",{}).get("route",[])
    visible=not route.is_empty() and progress.get("active",false)
    if not visible:return
    var p=state.get("position_ned_m",[0,0,0])
    position_m=Vector2(float(p[1]),-float(p[0]))
    var navigation=progress.get("navigation",{})
    var next_point=navigation.get("target_m",state.get("mission_route",{}).get("target_ned_m",[0,0]))
    target_m=Vector2(float(next_point[1]),-float(next_point[0]))
    extent=maxf(25,position_m.length()*1.2)
    for point in route:extent=maxf(extent,Vector2(float(point[0]),float(point[1])).length()*1.2)
    queue_redraw()

func project(point):
    return Vector2(size.x/2,size.y/2)+point*minf(size.x,size.y)*.42/extent

func _draw():
    draw_rect(Rect2(Vector2.ZERO,size),Color(.025,.055,.085,.9))
    var font=ThemeDB.fallback_font
    draw_string(font,Vector2(8,16),"N ↑  E →",HORIZONTAL_ALIGNMENT_LEFT,-1,11,Color(.5,.7,.8))
    draw_string(font,Vector2(8,size.y-6),"± %.0f m"%extent,HORIZONTAL_ALIGNMENT_LEFT,-1,10,Color(.5,.7,.8))
    var points=PackedVector2Array()
    for row in route:points.append(project(Vector2(float(row[1]),-float(row[0]))))
    if points.size()>1:draw_polyline(points,Color(.2,.5,.65),1.5,true)
    for i in range(points.size()):
        draw_circle(points[i],3,Color(.45,.7,.85))
        draw_string(font,points[i]+Vector2(4,-4),str(i),HORIZONTAL_ALIGNMENT_LEFT,-1,10,Color(.65,.78,.85))
    draw_arc(project(target_m),7,0,TAU,24,Color(1,.8,.3),2,true)
    var p=project(position_m)
    draw_colored_polygon(PackedVector2Array([p+Vector2(0,-6),p+Vector2(5,5),p+Vector2(-5,5)]),Color(.4,1,.78))
