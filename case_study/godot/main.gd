extends Node2D

## Companion renderer for the score-fiber replay. The browser inspector is canonical.
const BG := Color("#f5f6f1")
const INK := Color("#183038")
const MUTED := Color("#718184")
const TEAL := Color("#267a78")
const CORAL := Color("#cf705d")
const GOLD := Color("#b28735")
var step := 0
var revealed := false
var events := [
	{"time":"T-14d", "title":"Rare constraint is recorded", "action":"write", "access":"archived"},
	{"time":"T-10d", "title":"Routine memories dominate exposure", "action":"defer", "access":"candidate-starved"},
	{"time":"T-0", "title":"Lifecycle boundary arrives", "action":"defer", "access":"guarded-candidate"},
	{"time":"T+1", "title":"Reversible probe opens cold path", "action":"probe", "access":"temporary-restore"},
	{"time":"T+2", "title":"Answer remains reversible", "action":"answer", "access":"archived"}
]

func _ready() -> void:
	queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_SPACE:
			step = (step + 1) % events.size()
			queue_redraw()
		elif event.keycode == KEY_R:
			step = 0
			revealed = false
			queue_redraw()
		elif event.keycode == KEY_ENTER:
			revealed = true
			queue_redraw()

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, Vector2(1280, 720)), BG)
	draw_string(ThemeDB.fallback_font, Vector2(42, 52), "SQCAD / SCORE-FIBER REPLAY", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, MUTED)
	draw_string(ThemeDB.fallback_font, Vector2(42, 95), "Same observable evidence. Opposite possible futures.", HORIZONTAL_ALIGNMENT_LEFT, 900, 30, INK)
	draw_string(ThemeDB.fallback_font, Vector2(42, 126), "Space: advance   Enter: reveal branches   R: reset", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, MUTED)
	_draw_card(Rect2(42, 175, 360, 380), "VISIBLE EVIDENCE", TEAL)
	_draw_signal(Vector2(70, 240), "relevance", "0.71", TEAL)
	_draw_signal(Vector2(70, 300), "exposure", "low", CORAL)
	_draw_signal(Vector2(70, 360), "lineage", "sparse", GOLD)
	_draw_signal(Vector2(70, 420), "scope / version", "user-17 / v1", INK)
	_draw_card(Rect2(440, 175, 798, 380), "LATENT CONTINUATIONS", CORAL)
	_draw_tree_root(Rect2(744, 204, 190, 58))
	_draw_branch(Rect2(480, 245, 320, 190), "A", "rare evidence arrives", "probe / keep", TEAL, revealed)
	_draw_branch(Rect2(858, 245, 320, 190), "B", "rule is obsolete", "archive", CORAL, revealed)
	draw_line(Vector2(402, 365), Vector2(440, 365), GOLD, 3.0, true)
	draw_line(Vector2(839, 262), Vector2(640, 245), GOLD, 2.0, true)
	draw_line(Vector2(839, 262), Vector2(1018, 245), GOLD, 2.0, true)
	if revealed:
		draw_line(Vector2(640, 245), Vector2(640, 340), TEAL, 2.0, true)
		draw_line(Vector2(1018, 245), Vector2(1018, 340), CORAL, 2.0, true)
	else:
		draw_string(ThemeDB.fallback_font, Vector2(532, 490), "Press Enter after choosing an action in the browser.", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, MUTED)
	_draw_footer(events[step])

func _draw_card(rect: Rect2, label: String, accent: Color) -> void:
	draw_style_box(_box(Color("#fffefa"), Color("#d8dfda"), 1), rect)
	draw_rect(Rect2(rect.position + Vector2(18, 17), Vector2(22, 3)), accent)
	draw_string(ThemeDB.fallback_font, rect.position + Vector2(52, 25), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, MUTED)

func _draw_signal(position: Vector2, label: String, value: String, accent: Color) -> void:
	draw_circle(position, 5, accent)
	draw_string(ThemeDB.fallback_font, position + Vector2(16, 5), label, HORIZONTAL_ALIGNMENT_LEFT, 160, 12, INK)
	draw_string(ThemeDB.fallback_font, position + Vector2(190, 5), value, HORIZONTAL_ALIGNMENT_LEFT, 130, 12, accent)

func _draw_tree_root(rect: Rect2) -> void:
	draw_style_box(_box(INK, INK, 1), rect)
	draw_string(ThemeDB.fallback_font, rect.position + Vector2(48, 24), "SAME EVIDENCE", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color.WHITE)
	draw_string(ThemeDB.fallback_font, rect.position + Vector2(57, 45), "one visible state", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color("#cbd9d5"))

func _draw_branch(rect: Rect2, marker: String, title: String, optimal: String, accent: Color, is_revealed: bool) -> void:
	draw_style_box(_box(Color("#fffefa"), accent if is_revealed else Color("#d8dfda"), 1), rect)
	draw_circle(rect.position + Vector2(28, 30), 12, accent if is_revealed else Color("#d8dfda"))
	draw_string(ThemeDB.fallback_font, rect.position + Vector2(24, 35), marker, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color.WHITE if is_revealed else MUTED)
	draw_string(ThemeDB.fallback_font, rect.position + Vector2(55, 34), title, HORIZONTAL_ALIGNMENT_LEFT, 235, 15, INK)
	draw_string(ThemeDB.fallback_font, rect.position + Vector2(28, 94), "future label", HORIZONTAL_ALIGNMENT_LEFT, -1, 10, MUTED)
	draw_string(ThemeDB.fallback_font, rect.position + Vector2(28, 124), optimal if is_revealed else "???", HORIZONTAL_ALIGNMENT_LEFT, -1, 21, accent)

func _draw_footer(event: Dictionary) -> void:
	draw_rect(Rect2(42, 610, 1196, 48), INK)
	draw_string(ThemeDB.fallback_font, Vector2(60, 640), "%s   %s" % [event["time"], event["title"]], HORIZONTAL_ALIGNMENT_LEFT, 700, 13, Color.WHITE)
	draw_string(ThemeDB.fallback_font, Vector2(900, 640), "action: %s  /  access: %s" % [event["action"], event["access"]], HORIZONTAL_ALIGNMENT_LEFT, 320, 11, Color("#dcecea"))

func _box(fill: Color, border: Color, width: int) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.border_color = border
	box.set_border_width_all(width)
	return box
