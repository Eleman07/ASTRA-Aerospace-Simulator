extends SceneTree

const Main=preload("res://main.gd")

class TestMain extends Main:
    func _ready():pass
    func _process(_dt):pass

func _initialize():
    run.call_deferred()

func run():
    var app=TestMain.new()
    root.add_child(app)
    await process_frame
    app.make_interface()
    app.change_product_mode(1)
    assert(app.game_mode and app.mission_selection.item_count==3)
    assert(app.mission_selection.get_item_text(0)=="GIOCA · SPAZIO")
    assert(app.mission_selection.get_item_text(1)=="GIOCA · AEREO")
    assert(app.mission_selection.get_item_text(2)=="GIOCA · DRONE")
    assert(app.widgets.game_board.visible and not app.widgets.play.visible)
    app.change_product_mode(0)
    assert(not app.game_mode and app.mission_selection.item_count==6)
    assert(app.sas_selection.item_count==11)
    app.sas_hud.update_state({"supported":true,"enabled":true,"mode":"prograde","available_modes":["stability_assist","prograde","retrograde"],"markers":{}})
    assert(app.sas_hud.visible and app.sas_hud.toggle_button.text.contains("ON"))
    assert(app.sas_hud.mode_buttons.prograde.visible and app.sas_hud.mode_buttons.prograde.button_pressed)
    assert(not app.sas_hud.mode_buttons.target.visible and not app.sas_hud.mode_buttons.maneuver_node.visible)
    app.sas_hud.update_state({"supported":false})
    assert(app.sas_hud.visible)
    print("GIOCA UI PASS: 3 activity choices, career board entry, simulator list preserved, orbital SAS choices available")
    quit()
