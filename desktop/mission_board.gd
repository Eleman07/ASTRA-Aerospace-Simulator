extends "res://menu_window.gd"
## Paged native Gioca board. Mission content and unlock decisions belong to Python.
var host
var vehicle_kind="space"
var language="it"
var messages={}
var query_widgets={}
var rows_box
var detail_box
var count_label
var previous_button
var next_button
var offset=0
var total=0
var page_size=10
var revision=0
var selected_id=""
var debounce: Timer

func text_for(key):
    return str(messages.get(language,{}).get(key,key))

func setup(app,kind,locale="it"):
    host=app;vehicle_kind=kind;language=locale
    messages=JSON.parse_string(FileAccess.get_file_as_string("res://mission_i18n.json"))
    title="ASTRA · "+text_for("board")+" / "+kind.to_upper()
    size=Vector2i(1080,760);min_size=Vector2i(900,660)
    close_requested.connect(queue_free)
    host.add_child(self)
    build_ui();popup_centered();refresh()

func label(value,size_value=13,color=Color(.8,.88,.96)):
    var node=host.label_text(value,size_value,color)
    node.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
    return node

func option(parent,key,items):
    var control=OptionButton.new();control.size_flags_horizontal=Control.SIZE_EXPAND_FILL
    for entry in items:
        control.add_item(entry[0]);control.set_item_metadata(control.item_count-1,entry[1])
    parent.add_child(control);query_widgets[key]=control
    control.item_selected.connect(func(_i):offset=0;refresh())
    return control

func build_ui():
    var margin=MarginContainer.new();margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    for edge in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+edge,18)
    add_child(margin)
    var box=VBoxContainer.new();box.add_theme_constant_override("separation",10);margin.add_child(box)
    var header=HBoxContainer.new();box.add_child(header)
    var heading=label(text_for("board")+"  /  "+vehicle_kind.to_upper(),22,Color(.55,.85,1));heading.size_flags_horizontal=Control.SIZE_EXPAND_FILL;header.add_child(heading)
    var locale=OptionButton.new();locale.add_item("Italiano");locale.add_item("English");locale.select(1 if language=="en" else 0);header.add_child(locale)
    locale.item_selected.connect(func(index):
        host.game_language="en" if index==1 else "it"
        host.request("/desktop/game/preferences",{"language":host.game_language})
        host.show_game_missions(vehicle_kind);queue_free())
    var account=host.game_career
    box.add_child(label("%s: %s  ·  %s: %s  ·  %s: %s"%[text_for("credits"),str(account.get("credits",0)),text_for("reputation"),str(account.get("reputation",0)),text_for("science"),str(account.get("science",0))],13,Color(.55,.86,.74)))
    var first=HBoxContainer.new();box.add_child(first)
    var search=LineEdit.new();search.placeholder_text=text_for("search");search.size_flags_horizontal=Control.SIZE_EXPAND_FILL;first.add_child(search);query_widgets.query=search
    option(first,"source",[[text_for("all"),"all"],[text_for("story"),"story"],[text_for("contracts"),"contracts"],[text_for("daily"),"daily"],[text_for("weekly"),"weekly"],[text_for("favorites"),"favorites"],[text_for("recent"),"recent"]])
    debounce=Timer.new();debounce.one_shot=true;debounce.wait_time=.3;add_child(debounce)
    search.text_changed.connect(func(_value):debounce.start())
    debounce.timeout.connect(func():offset=0;refresh())
    var filters=HBoxContainer.new();box.add_child(filters)
    option(filters,"difficulty",[[text_for("difficulty"),0],["★  1",1],["★★  2",2],["★★★  3",3],["★★★★  4",4],["★★★★★  5",5]])
    option(filters,"max_duration_s",[[text_for("duration"),0],["≤ 5 min",300],["≤ 10 min",600],["≤ 20 min",1200],["≤ 30 min",1800]])
    option(filters,"family",[[text_for("type"),""]])
    option(filters,"sort",[[text_for("sort_difficulty"),"difficulty"],[text_for("sort_duration"),"duration"],[text_for("sort_reward"),"reward"]])
    var split=HSplitContainer.new();split.size_flags_vertical=Control.SIZE_EXPAND_FILL;split.split_offset=440;box.add_child(split)
    var list_scroll=ScrollContainer.new();list_scroll.custom_minimum_size.x=430;list_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;split.add_child(list_scroll)
    rows_box=VBoxContainer.new();rows_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;rows_box.add_theme_constant_override("separation",7);list_scroll.add_child(rows_box)
    var detail_scroll=ScrollContainer.new();detail_scroll.custom_minimum_size.x=400;detail_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;split.add_child(detail_scroll)
    detail_box=VBoxContainer.new();detail_box.size_flags_horizontal=Control.SIZE_EXPAND_FILL;detail_box.add_theme_constant_override("separation",10);detail_scroll.add_child(detail_box)
    detail_box.add_child(label(text_for("select")))
    var navigation=HBoxContainer.new();box.add_child(navigation)
    previous_button=host.button(text_for("previous"),func():offset=maxi(0,offset-page_size);refresh(),navigation)
    count_label=label(text_for("loading"));count_label.size_flags_horizontal=Control.SIZE_EXPAND_FILL;count_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;navigation.add_child(count_label)
    next_button=host.button(text_for("next"),func():offset+=page_size;refresh(),navigation)

func clear(container):
    for child in container.get_children():container.remove_child(child);child.queue_free()

func refresh():
    revision+=1
    var serial=revision
    var payload={"vehicle":vehicle_kind,"language":language,"query":query_widgets.query.text,"offset":offset,"limit":page_size}
    for key in ["source","difficulty","max_duration_s","family","sort"]:
        var control=query_widgets[key];payload[key]=control.get_item_metadata(control.selected)
    count_label.text=text_for("loading")
    var reply=await host.request("/desktop/game/catalog",payload)
    if not is_instance_valid(self) or serial!=revision:return
    clear(rows_box)
    if reply.has("error"):rows_box.add_child(label(str(reply.error)));return
    var metadata=reply.get("_meta",{})
    var missions=reply.get(vehicle_kind,[])
    total=int(metadata.get("total",missions.size()))
    previous_button.disabled=offset==0;next_button.disabled=offset+page_size>=total
    count_label.text="%d–%d / %d %s"%[offset+1 if total else 0,mini(offset+missions.size(),total),total,text_for("count")]
    if query_widgets.family.item_count==1:
        for family in metadata.get("families",[]):
            if family is Dictionary:
                query_widgets.family.add_item(str(family.get("label",family.get("id",""))));query_widgets.family.set_item_metadata(query_widgets.family.item_count-1,family.get("id",""))
            else:
                query_widgets.family.add_item(str(family).replace("_"," "));query_widgets.family.set_item_metadata(query_widgets.family.item_count-1,family)
    if missions.is_empty():rows_box.add_child(label(text_for("empty")))
    for mission in missions:
        var card=Button.new();card.alignment=HORIZONTAL_ALIGNMENT_LEFT;card.custom_minimum_size.y=91
        card.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
        var status=str(mission.get("medal",mission.get("status","new")))
        if status=="":status=str(mission.get("status","new"))
        card.text=("★ " if mission.get("favorite",false) else "")+str(mission.title)+"\n"+"★".repeat(int(mission.get("difficulty",1)))+"  ·  %d min  ·  ¤ %d  ·  %s"%[ceili(float(mission.get("duration_s",0))/60),int(mission.reward.credits),text_for(status)]
        card.tooltip_text=str(mission.briefing)
        card.pressed.connect(func():show_mission(mission))
        rows_box.add_child(card)
    if not missions.is_empty():
        var selected=missions[0]
        for mission in missions:
            if str(mission.id)==selected_id:selected=mission
        show_mission(selected)

func show_mission(mission):
    selected_id=str(mission.id);clear(detail_box)
    detail_box.add_child(label(str(mission.get("campaign",text_for("contract"))),11,Color(.4,.75,1)))
    detail_box.add_child(label(str(mission.title),22,Color(.9,.96,1)))
    detail_box.add_child(label(text_for("brief"),11,Color(.4,.75,1)))
    detail_box.add_child(label(str(mission.briefing),14))
    detail_box.add_child(label(text_for("objectives"),11,Color(.4,.75,1)))
    for objective in mission.objectives:detail_box.add_child(label("○  "+str(objective.label),14))
    for objective in mission.get("optional_objectives",[]):detail_box.add_child(label("☆  "+str(objective.get("label","")),12,Color(.9,.78,.5)))
    var constraints=mission.get("constraints",{})
    if not constraints.is_empty():
        detail_box.add_child(label(text_for("constraints"),11,Color(.4,.75,1)))
        for key in constraints:
            detail_box.add_child(label(text_for(key)+": "+host.format_number(constraints[key])+(" %" if key=="min_resource_pct" else ""),12))
    var bonus=mission.get("bonus",{})
    if not bonus.is_empty():
        detail_box.add_child(label(text_for("bonus"),11,Color(.95,.8,.4)))
        for key in bonus:detail_box.add_child(label("☆  "+text_for(key)+": "+host.format_number(bonus[key])+(" %" if key=="min_resource_pct" else ""),12))
        detail_box.add_child(label(text_for("medal_rules"),11))
    var reward=mission.reward
    detail_box.add_child(label(text_for("reward")+"  ¤ %d  ·  REP %d  ·  SCI %d"%[int(reward.credits),int(reward.reputation),int(reward.science)],13,Color(.5,.9,.74)))
    var requirements=mission.get("requires",[])
    if not requirements.is_empty():
        var descriptions=[]
        for requirement in requirements:descriptions.append(text_for(requirement))
        detail_box.add_child(label(text_for("requirements")+": "+", ".join(descriptions),12))
    var launch=host.button(text_for("locked") if mission.get("locked",false) else text_for("launch"),func():host.start_game_mission(str(mission.id),self),detail_box)
    launch.disabled=mission.get("locked",false)
    host.button(text_for("unfavorite") if mission.get("favorite",false) else text_for("favorite"),func():
        var reply=await host.request("/desktop/game/favorite",{"mission_id":mission.id,"favorite":not mission.get("favorite",false)})
        if reply.has("error"):host.report_result(reply)
        else:refresh(),detail_box)
