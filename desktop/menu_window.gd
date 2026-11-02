extends Window

var hotas_input_router=Callable()

func _input(event):
    if hotas_input_router.is_valid() and hotas_input_router.call(event):
        set_input_as_handled()

func _unhandled_input(event):
    # Let a focused dropdown/file control handle cancel first. If no control
    # consumes it, B/Escape closes this panel and returns to the flight view.
    if event.is_action_pressed("ui_cancel"):
        set_input_as_handled()
        hide()
        queue_free()
