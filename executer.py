from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QListWidget, QListWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsPolygonItem, QSizePolicy, QFrame,
)
from PySide6.QtGui import (
    QColor, QFont, QPen, QBrush, QPolygonF, QFontMetrics,
)
import qtawesome as qta
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF


BG_DEEP    = "#1e1e1e"
BG_PANEL   = "#252526"
BG_CARD    = "#2d2d2d"
BG_INPUT   = "#3c3c3c"

ACCENT_BLUE   = "#4fc1ff"
ACCENT_GREEN  = "#4ec9b0"
ACCENT_RED    = "#f44747"
ACCENT_YELLOW = "#dcdcaa"
ACCENT_CYAN   = "#9cdcfe"
ACCENT_PURPLE = "#c586c0"

TEXT_PRIMARY = "#d4d4d4"
TEXT_MUTED   = "#858585"
BORDER       = "#3d3d3d"

CELL_W        = 54
CELL_H        = 54
CELL_GAP      = 2
VISIBLE_CELLS = 15


class TapeNode:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.prev: "TapeNode | None" = None
        self.next: "TapeNode | None" = None


class LinkedTape:
    def __init__(self, symbols: str, null: str):
        self.null = null
        self._origin: TapeNode = TapeNode(null)
        self._head_node: TapeNode = self._origin
        self._head_pos: int = 0

        node = self._origin
        for ch in symbols:
            node.symbol = ch
            nxt = TapeNode(null)
            node.next = nxt
            nxt.prev = node
            node = nxt
        self._origin.symbol = symbols[0] if symbols else null
        if len(symbols) > 1:
            cur = self._origin
            for ch in symbols[1:]:
                nxt = TapeNode(ch)
                cur.next = nxt
                nxt.prev = cur
                cur = nxt

    def _rebuild(self, symbols: str):
        self._origin = TapeNode(self.null)
        if not symbols:
            self._head_node = self._origin
            self._head_pos  = 0
            return
        self._origin.symbol = symbols[0]
        cur = self._origin
        for ch in symbols[1:]:
            nxt = TapeNode(ch)
            cur.next = nxt
            nxt.prev = cur
            cur = nxt
        self._head_node = self._origin
        self._head_pos  = 0

    def read(self) -> str:
        return self._head_node.symbol

    def write(self, symbol: str):
        self._head_node.symbol = symbol

    def move_right(self):
        if self._head_node.next is None:
            nxt = TapeNode(self.null)
            nxt.prev = self._head_node
            self._head_node.next = nxt
        self._head_node = self._head_node.next
        self._head_pos += 1

    def move_left(self):
        if self._head_node.prev is None:
            prv = TapeNode(self.null)
            prv.next = self._head_node
            self._head_node.prev = prv
            self._origin = prv
            self._head_pos = 0
        else:
            self._head_pos -= 1
        self._head_node = self._head_node.prev

    def head_pos(self) -> int:
        return self._head_pos

    def to_list(self) -> list[str]:
        result = []
        node = self._origin
        while node is not None:
            result.append(node.symbol)
            node = node.next
        return result

    def snapshot(self) -> tuple[list[str], int]:
        return self.to_list(), self._head_pos

    def restore(self, symbols: list[str], pos: int):
        self._rebuild("".join(symbols))
        cur = self._origin
        for _ in range(pos):
            if cur.next is None:
                nxt = TapeNode(self.null)
                nxt.prev = cur
                cur.next = nxt
            cur = cur.next
        self._head_node = cur
        self._head_pos  = pos


class TMStack:
    def __init__(self):
        self._data: list = []

    def push(self, item):
        self._data.append(item)

    def pop(self):
        return self._data.pop() if self._data else None

    def peek(self):
        return self._data[-1] if self._data else None

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def size(self) -> int:
        return len(self._data)


class TMEngine:
    def __init__(self, transitions: dict, start: str, accept: str, reject: str, tape: str, null: str):
        self.null        = null
        self.transitions = transitions
        self.accept      = accept
        self.reject      = reject
        self.start       = start
        self.state       = start
        self.halted      = False
        self.accepted    = False
        self.step_count  = 0
        self._tape       = LinkedTape(tape if tape else null, null)
        self._history    = TMStack()

    def _save(self):
        tape_snap, pos = self._tape.snapshot()
        self._history.push({
            "state":      self.state,
            "tape":       tape_snap,
            "head":       pos,
            "halted":     self.halted,
            "accepted":   self.accepted,
            "step_count": self.step_count,
        })

    def step(self) -> dict | None:
        if self.halted:
            return None

        self._save()

        symbol = self._tape.read()
        key    = (self.state, symbol)

        if key not in self.transitions:
            self.halted   = True
            self.accepted = (self.state == self.accept)
            return {
                "step":     self.step_count,
                "from":     self.state,
                "read":     symbol,
                "to":       self.state,
                "write":    symbol,
                "dir":      "_",
                "halted":   True,
                "accepted": self.accepted,
            }

        next_state, write, direction = self.transitions[key]
        self._tape.write(write)

        if direction == ">":
            self._tape.move_right()
        elif direction == "<":
            self._tape.move_left()

        prev_state  = self.state
        self.state  = next_state
        self.step_count += 1

        if self.state in (self.accept, self.reject):
            self.halted   = True
            self.accepted = (self.state == self.accept)

        return {
            "step":     self.step_count,
            "from":     prev_state,
            "read":     symbol,
            "to":       next_state,
            "write":    write,
            "dir":      direction,
            "halted":   self.halted,
            "accepted": self.accepted,
        }

    def step_back(self) -> bool:
        snap = self._history.pop()
        if snap is None:
            return False
        self.state       = snap["state"]
        self.halted      = snap["halted"]
        self.accepted    = snap["accepted"]
        self.step_count  = snap["step_count"]
        self._tape.restore(snap["tape"], snap["head"])
        return True

    def can_step_back(self) -> bool:
        return not self._history.is_empty()

    @property
    def tape(self) -> list[str]:
        return self._tape.to_list()

    @property
    def head(self) -> int:
        return self._tape.head_pos()

    def reset(self, tape: str):
        self._tape       = LinkedTape(tape if tape else self.null, self.null)
        self.state       = self.start
        self.halted      = False
        self.accepted    = False
        self.step_count  = 0
        self._history    = TMStack()


class TapeView(QGraphicsView):
    def __init__(self, null, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.null   = null
        self.setScene(self._scene)
        self.setFixedHeight(CELL_H + 40)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QGraphicsView {{
                background: {BG_DEEP};
                border: none;
                border-radius: 6px;
            }}
        """)
        self.setRenderHint(self.renderHints().Antialiasing)
        self._cells: list  = []
        self._pointer: QGraphicsPolygonItem | None = None
        self._font = QFont("Consolas", 16, QFont.Weight.Bold)

    def render_tape(self, tape: list[str], head: int):
        self._scene.clear()
        self._cells   = []
        self._pointer = None

        half  = VISIBLE_CELLS // 2
        start = max(0, head - half)
        end   = start + VISIBLE_CELLS
        while len(tape) < end:
            tape.append(self.null)

        total_w  = VISIBLE_CELLS * (CELL_W + CELL_GAP) - CELL_GAP
        offset_x = 0

        for i, tape_idx in enumerate(range(start, end)):
            x      = offset_x + i * (CELL_W + CELL_GAP)
            active = (tape_idx == head)

            rect = QGraphicsRectItem(QRectF(x, 0, CELL_W, CELL_H))
            if active:
                rect.setBrush(QBrush(QColor("#1e3a5f")))
                rect.setPen(QPen(QColor(ACCENT_BLUE), 2))
            else:
                rect.setBrush(QBrush(QColor(BG_CARD)))
                rect.setPen(QPen(QColor(BORDER), 1))
            self._scene.addItem(rect)

            sym   = tape[tape_idx] if tape_idx < len(tape) else self.null
            label = QGraphicsTextItem(sym)
            label.setFont(self._font)
            color = ACCENT_BLUE if active else (TEXT_MUTED if sym == self.null else TEXT_PRIMARY)
            label.setDefaultTextColor(QColor(color))
            br = label.boundingRect()
            label.setPos(x + (CELL_W - br.width()) / 2, (CELL_H - br.height()) / 2)
            self._scene.addItem(label)

            if active:
                cx  = x + CELL_W / 2
                ty  = CELL_H + 4
                tri = QPolygonF([
                    QPointF(cx - 8, ty),
                    QPointF(cx + 8, ty),
                    QPointF(cx,     ty + 12),
                ])
                self._pointer = QGraphicsPolygonItem(tri)
                self._pointer.setBrush(QBrush(QColor(ACCENT_BLUE)))
                self._pointer.setPen(QPen(Qt.PenStyle.NoPen))
                self._scene.addItem(self._pointer)

        self._scene.setSceneRect(QRectF(0, 0, total_w, CELL_H + 20))
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._scene.sceneRect().isValid():
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.IgnoreAspectRatio)


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 6px;
        }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(8)
    if title:
        hdr = QLabel(title)
        hdr.setStyleSheet(f"""
            color: {TEXT_MUTED};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(hdr)
    return card, layout


def _label(text: str, color: str = TEXT_PRIMARY, size: int = 12, bold: bool = False) -> QLabel:
    lbl    = QLabel(text)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(f"""
        color: {color};
        font-size: {size}px;
        font-weight: {weight};
        background: transparent;
        border: none;
    """)
    return lbl


def _btn(text: str, bg: str = BG_INPUT, fg: str = TEXT_PRIMARY, border: str = BORDER) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: 5px;
            padding: 6px 16px;
            font-weight: bold;
            font-size: 12px;
        }}
        QPushButton:hover   {{ background: {bg}cc; }}
        QPushButton:pressed  {{ background: {bg}88; }}
        QPushButton:disabled {{
            background: {BG_CARD};
            color: {TEXT_MUTED};
            border-color: {BORDER};
        }}
    """)
    return b


class _ScalingLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_font()

    def setText(self, text):
        super().setText(text)
        self._fit_font()

    def _fit_font(self):
        if not self.text():
            return
        w = self.width() - 8
        h = self.height() - 8
        if w <= 0 or h <= 0:
            return
        size = 28
        while size > 6:
            font = QFont("Consolas", size, QFont.Weight.Bold)
            fm   = QFontMetrics(font)
            if fm.horizontalAdvance(self.text()) <= w and fm.height() <= h:
                break
            size -= 1
        self.setFont(font)


class ExecutionDialog(QDialog):
    def __init__(self, tm_data: dict, tape_input: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Running...")
        self.setMinimumSize(900, 620)
        self.setStyleSheet(f"""
            QDialog {{ background: {BG_PANEL}; }}
            QScrollBar:vertical {{
                background: {BG_DEEP}; width: 6px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: #424242; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}
        """)

        self._engine     = self._build_engine(tm_data, tape_input)
        self._tape_input = tape_input or self.null
        self._timer      = QTimer(self)
        self._timer.timeout.connect(self._auto_step)

        self._build_ui()
        self._refresh()

    def _build_engine(self, data: dict, tape: str) -> TMEngine:
        transitions = {}
        for state, rules in data["states"].items():
            for symbol, (nxt, write, direction) in rules.items():
                transitions[(state, symbol)] = (nxt, write, direction)
        self.null = data["null"]
        return TMEngine(transitions, data["start"], data["accept"], data["reject"], tape, self.null)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        tape_card, tape_layout = _card("Tape")
        self._tape_view = TapeView(self.null)
        self._tape_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tape_layout.addWidget(self._tape_view)
        root.addWidget(tape_card)

        mid = QHBoxLayout()
        mid.setSpacing(12)
        mid.addWidget(self._build_state_card(), 1)
        mid.addWidget(self._build_controls_card(), 3)
        mid.addWidget(self._build_log_card(), 2)
        root.addLayout(mid, 1)

        self._banner = QLabel("Ready")
        self._banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._banner.setStyleSheet(f"""
            background: #0d2a1a; color: {ACCENT_GREEN};
            border: 1px solid #166534; border-radius: 5px;
            padding: 8px; font-weight: bold; font-size: 13px;
        """)
        root.addWidget(self._banner)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = _btn("Close", BG_INPUT, TEXT_MUTED)
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self._on_close)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

    def _build_state_card(self) -> QFrame:
        card, layout = _card("Current state")
        card.setMinimumWidth(130)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._state_label = _ScalingLabel("—")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._state_label.setStyleSheet(f"color: {ACCENT_BLUE}; background: transparent; border: none;")
        self._state_label.setWordWrap(True)
        layout.addWidget(self._state_label, 1)

        self._step_label = _label("Step: 0", TEXT_MUTED, 10)
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._step_label)

        self._head_label = _label("Head: 0", TEXT_MUTED, 10)
        self._head_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._head_label)

        return card

    def _build_controls_card(self) -> QFrame:
        card, layout = _card("Controls")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_run   = _btn("", "#2ea043", "#ffffff", "#2ea043")
        self._btn_pause = _btn("", BG_INPUT, ACCENT_YELLOW)
        self._btn_back  = _btn("", BG_INPUT, ACCENT_PURPLE)
        self._btn_step  = _btn("", BG_INPUT, ACCENT_CYAN)
        self._btn_reset = _btn("", BG_INPUT, ACCENT_RED)

        self._btn_run.setIcon(qta.icon("fa5s.play"))
        self._btn_pause.setIcon(qta.icon("fa6s.pause"))
        self._btn_back.setIcon(qta.icon("fa5s.step-backward"))
        self._btn_step.setIcon(qta.icon("fa5s.step-forward"))
        self._btn_reset.setIcon(qta.icon("fa6s.arrow-rotate-left"))

        self._btn_pause.setEnabled(False)
        self._btn_back.setEnabled(False)

        for b in (self._btn_run, self._btn_pause, self._btn_back, self._btn_step, self._btn_reset):
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_row.addWidget(b)

        layout.addLayout(btn_row)
        layout.addStretch()

        spd_row = QHBoxLayout()
        spd_row.setSpacing(8)
        spd_row.addWidget(_label("Slow", TEXT_MUTED, 10))

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(1, 10)
        self._slider.setValue(5)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {BG_INPUT}; height: 6px; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {TEXT_PRIMARY};
                width: 14px; height: 14px; margin: -4px 0; border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT_BLUE}; border-radius: 3px;
            }}
        """)
        spd_row.addWidget(self._slider, 1)
        spd_row.addWidget(_label("Fast", TEXT_MUTED, 10))
        layout.addLayout(spd_row)

        self._btn_run.clicked.connect(self._on_run)
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_back.clicked.connect(self._on_back)
        self._btn_step.clicked.connect(self._on_step)
        self._btn_reset.clicked.connect(self._on_reset)

        return card

    def _build_log_card(self) -> QFrame:
        card, layout = _card("Logs")
        card.setMinimumWidth(200)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self._log = QListWidget()
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._log.setStyleSheet(f"""
            QListWidget {{
                background: {BG_DEEP}; color: {TEXT_PRIMARY};
                border: none; font-size: 11px;
                font-family: 'Consolas', monospace;
            }}
            QListWidget::item {{
                padding: 3px 6px; border-bottom: 1px solid {BORDER};
            }}
            QListWidget::item:selected {{ background: #264f78; }}
        """)
        layout.addWidget(self._log)
        return card

    def _refresh(self):
        eng = self._engine
        self._tape_view.render_tape(eng.tape, eng.head)
        self._state_label.setText(eng.state)
        self._step_label.setText(f"Step: {eng.step_count}")
        self._head_label.setText(f"Head: {eng.head}")

        if eng.state == eng.accept:
            color = ACCENT_GREEN
        elif eng.state == eng.reject:
            color = ACCENT_RED
        else:
            color = ACCENT_BLUE
        self._state_label.setStyleSheet(f"color: {color}; background: transparent; border: none;")

        self._btn_back.setEnabled(eng.can_step_back() and not self._timer.isActive())

        if eng.halted:
            if eng.accepted:
                self._banner.setText("Accepted")
                self._banner.setStyleSheet(f"""
                    background: #0d2a1a; color: {ACCENT_GREEN};
                    border: 1px solid #166534; border-radius: 5px;
                    padding: 8px; font-weight: bold; font-size: 13px;
                """)
            else:
                self._banner.setText("Rejected")
                self._banner.setStyleSheet(f"""
                    background: #2a0d0d; color: {ACCENT_RED};
                    border: 1px solid #7f1d1d; border-radius: 5px;
                    padding: 8px; font-weight: bold; font-size: 13px;
                """)
            self._stop_timer()
        else:
            self._banner.setText(f"Running   |   Step: {eng.step_count}")

    def _log_entry(self, entry: dict):
        step  = entry["step"]
        frm   = entry["from"]
        read  = entry["read"]
        to    = entry["to"]
        write = entry["write"]
        d     = entry["dir"]
        text  = f"#{step}  ({frm}, {read}) → ({to}, {write}, {d})"
        item  = QListWidgetItem(text)
        if entry.get("halted"):
            color = ACCENT_GREEN if entry.get("accepted") else ACCENT_RED
        else:
            color = TEXT_PRIMARY
        item.setForeground(QColor(color))
        self._log.addItem(item)
        self._log.scrollToBottom()

    def _on_run(self):
        if self._engine.halted:
            return
        self._btn_run.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_step.setEnabled(False)
        self._btn_back.setEnabled(False)
        interval = max(50, 1100 - self._slider.value() * 100)
        self._timer.start(interval)

    def _on_pause(self):
        self._stop_timer()

    def _on_back(self):
        if not self._engine.can_step_back():
            return
        self._engine.step_back()
        if self._log.count() > 0:
            self._log.takeItem(self._log.count() - 1)
        self._refresh()

    def _on_step(self):
        if self._engine.halted:
            return
        entry = self._engine.step()
        if entry:
            self._log_entry(entry)
        self._refresh()

    def _on_reset(self):
        self._stop_timer()
        self._engine.reset(self._tape_input)
        self._log.clear()
        self._banner.setText("Ready")
        self._banner.setStyleSheet(f"""
            background: #0d2a1a; color: {ACCENT_GREEN};
            border: 1px solid #166534; border-radius: 5px;
            padding: 8px; font-weight: bold; font-size: 13px;
        """)
        self._btn_run.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_step.setEnabled(True)
        self._btn_back.setEnabled(False)
        self._refresh()

    def _on_close(self):
        self._stop_timer()
        self.accept()

    def _auto_step(self):
        if self._engine.halted:
            self._stop_timer()
            self._refresh()
            return
        entry = self._engine.step()
        if entry:
            self._log_entry(entry)
        self._refresh()
        interval = max(50, 1100 - self._slider.value() * 100)
        self._timer.setInterval(interval)

    def _stop_timer(self):
        self._timer.stop()
        self._btn_run.setEnabled(not self._engine.halted)
        self._btn_pause.setEnabled(False)
        self._btn_step.setEnabled(not self._engine.halted)
        self._btn_back.setEnabled(self._engine.can_step_back())

    def closeEvent(self, event):
        self._stop_timer()
        super().closeEvent(event)