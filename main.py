import sys
import os
import re
import qtawesome as qta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QPlainTextEdit, QLineEdit, QLabel, 
    QToolBar, QPushButton, QSizePolicy, QTextEdit
)
from PySide6.QtGui import (
    QFont, QColor, QSyntaxHighlighter, QTextCharFormat,
    QPalette, QPainter
)
from PySide6.QtCore import QRect, QSize, Qt, QRegularExpression

BG_DEEP    = "#1e1e1e"  # editor background
BG_PANEL   = "#252526"  # sidebar / panels
BG_CARD    = "#2d2d2d"  # cards, inputs
BG_INPUT   = "#3c3c3c"  # input fields
BG_ROW_ALT = "#2a2a2a"  # alternating table rows
BG_GUTTER  = "#1e1e1e"  # gutter same as editor

ACCENT_BLUE   = "#4fc1ff"  # variables / properties
ACCENT_PURPLE = "#c586c0"  # keywords (if, return, etc.)
ACCENT_GREEN  = "#4ec9b0"  # types / classes
ACCENT_RED    = "#f44747"  # errors
ACCENT_YELLOW = "#dcdcaa"  # functions
ACCENT_CYAN   = "#9cdcfe"  # parameters / locals

TEXT_PRIMARY = "#d4d4d4"   # default text
TEXT_MUTED   = "#858585"   # comments, line numbers
TEXT_DIM     = "#4b4b4b"   # very dim, inactive
BORDER       = "#3d3d3d"   # borders, separators

globalCss = """
    QMainWindow, QWidget {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        font-size: 12px;
    }}
    QScrollBar:vertical {{
        background: {BG_DEEP};
        width: 8px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background: #424242;
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar:horizontal {{
        background: {BG_DEEP};
        height: 8px;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background: {BG_CARD};
        border-radius: 4px;
        min-width: 20px;
    }}
    QSplitter::handle {{
        background: {BORDER};
    }}
    QToolTip {{
        background: {BG_CARD};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        padding: 4px;
    }}
    """


class SyntaxHigh(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        def fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold: f.setFontWeight(700)
            if italic: f.setFontItalic(True)
            return f

        self._rules.insert(0, (
            QRegularExpression(r"\b[a-zA-Z][a-zA-Z0-9]*\b"),
            fmt("#9cdcfe"),
        ))
        for kw in ("alphabet", "start", "accept", "reject", "null"):
            self._rules.append((
                QRegularExpression(rf"\b{kw}\b"),
                fmt("#569cd6", bold=True),
            ))
        self._rules.append((
            QRegularExpression(r"=>"),
            fmt("#c586c0", bold=True),
        ))
        self._rules.append((
            QRegularExpression(r"=(?!>)"),
            fmt(ACCENT_YELLOW),
        ))
        self._rules.append((
            QRegularExpression(r"(?<!=)>|<"),
            fmt("#4fc1ff"),
        ))
        self._rules.append((
            QRegularExpression(r"[\[\](),]"),
            fmt("#d4d4d4"),
        ))
        self._rules.append((
            QRegularExpression(r"//[^\n]*"),
            fmt("#6a9955", italic=True),
        ))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

class _GutterArea(QWidget):
    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.gutter_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    PADDING = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gutter = _GutterArea(self)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter_scroll)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_gutter_width()
        self._highlight_current_line()
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {BG_DEEP};
                color: {TEXT_PRIMARY};
                border: none;
                selection-background-color: #264f78;
                selection-color: #d4d4d4;
                padding-left: 4px;
                font-size: 14px;
                padding-left: 8px;
                padding-top: 4px;
                line-height: 1.8;
            }}
        """)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.setFont(font)
        self.document().setDefaultStyleSheet("p { line-height: 160%; }")
        self.setTabStopDistance(32)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font.setPointSize(12)
        self.setTabStopDistance(40)

    def gutter_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return self.PADDING * 2 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter_scroll(self, rect, dy):
        if dy: self._gutter.scroll(0, dy)
        else: self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()): self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event):
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor(BG_GUTTER))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(TEXT_DIM))
                painter.drawText(
                    0, top,
                    self._gutter.width() - self.PADDING // 2,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            number += 1

    def _highlight_current_line(self):
        extra: list = []
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor("#2a2d2e"))
        sel.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        extra.append(sel)
        self.setExtraSelections(extra)


class TMParser:
    def __init__(self):
        self.data = {"states":{}}
    def parse(self, code):
        lines = code.split("\n")
        stateReg = r"\(\s*(\b[a-zA-Z][a-zA-Z0-9]*\b),\s*(\w+)\)\s*=>\s*\(\s*(\b[a-zA-Z][a-zA-Z0-9]*\b),\s*(\w+),\s*([><_])\)"
        for i in lines:
            if (ret:=re.search(stateReg, i)):
                if not ret.group(1) in self.data["states"]: self.data["states"][ret.group(1)] = {}
                self.data["states"][ret.group(1)][ret.group(2)] = (ret.group(3), ret.group(4), ret.group(5))
            elif (ret:=re.search(r"^alphabet\s*=\s*\[([^\]]*)\]", i)):
                if "alphabet" in self.data: 
                    raise ValueError("Double declaration of alphabet")
                self.data["alphabet"] = [s.strip() for s in ret.group(1).split(",")]
            elif (ret:=re.search(r"^start\s*=\s*([a-zA-Z][a-zA-Z0-9]*)", i)):
                if "start" in self.data: 
                    raise ValueError("Double declaration of start state")
                self.data["start"] = ret.group(1)
            elif (ret:=re.search(r"^accept\s*=\s*([a-zA-Z][a-zA-Z0-9]*)", i)):
                if "accept" in self.data: 
                    raise ValueError("Double declaration of accept state")
                self.data["accept"] = ret.group(1)
            elif (ret:=re.search(r"^reject\s*=\s*([a-zA-Z][a-zA-Z0-9]*)", i)):
                if "reject" in self.data: 
                    raise ValueError("Double declaration of reject state")
                self.data["reject"] = ret.group(1)
            elif (ret:=re.search(r"^null\s*=\s*(\w+)", i)):
                if "null" in self.data: 
                    raise ValueError("Double declaration of null symbol")
                self.data["null"] = ret.group(1)
        return self.data

    def validate(self):
        errors = []
        if "start" not in self.data:
            errors.append("'start' state is not defined")
        if "accept" not in self.data:
            errors.append("'accept' state is not defined")
        if "reject" not in self.data:
            errors.append("'reject' state is not defined")
        if "null" not in self.data:
            errors.append("'null' symbol is not defined")
        if "alphabet" not in self.data:
            errors.append("'alphabet' is not defined")
        if not self.data["states"]:
            errors.append("No state defined")
        if errors:
            raise Exception("\n".join(f"- {e}" for e in errors))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Turing Machine Simulator")
        self.resize(1200, 780)
        self.setStyleSheet(globalCss)
        mb = self.menuBar()
        mb.setStyleSheet(f"""
            QMenuBar {{
                background: {BG_DEEP};
                color: {ACCENT_BLUE};
                border-bottom: 1px solid {BORDER};
                padding: 2px 4px;
            }}
            QMenuBar::item:selected {{
                background: {BG_CARD};
                border-radius: 4px;
            }}
            QMenu {{
                background: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
            }}
            QMenu::item:selected {{
                background: {ACCENT_BLUE};
                color: white;
            }}
        """)

        file_menu = mb.addMenu("File")
        file_menu.addAction("New",  self._action_new,  "Ctrl+N")
        file_menu.addAction("Open", self._action_open, "Ctrl+O")
        file_menu.addAction("Save", self._action_save, "Ctrl+S")
        file_menu.addSeparator()
        file_menu.addAction("Quit", self.close, "Ctrl+Q")

        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setStyleSheet(f"""
            QToolBar {{
                background: {BG_CARD};
                border-bottom: 1px solid {BORDER};
                padding: 4px 8px;
                spacing: 6px;
            }}
        """)
        self.addToolBar(tb)

        self.fileName = QLabel("Untitled")
        self.fileName.setFont(QFont("Verdana", 9))
        self.fileName.setContentsMargins(16, 0, 0, 0)
        tb.addWidget(self.fileName)

        tb.addSeparator()

        tape_lbl = QLabel("Input:")
        tape_lbl.setStyleSheet(f"color: {TEXT_MUTED}; padding: 0px 4px 0px 8px;")
        tb.addWidget(tape_lbl)

        self.tapeInput = QLineEdit()
        self.tapeInput.setFixedWidth(160)
        self.tapeInput.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT_BLUE};
            }}
        """)
        tb.addWidget(self.tapeInput)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.runButton = QPushButton()
        self.runButton.setIcon(qta.icon("fa5s.play"))
        self.runButton.setStyleSheet("""
            QPushButton {
                background-color: #2ea043;
                color: #ffffff;
                border: 1px solid #2ea043;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 500;
                margin: 0px 7px 0px 0px;
            }
            QPushButton:hover {
                background-color: #3fb950;
                border: 1px solid #3fb950;
            }
            QPushButton:pressed {
                background-color: #238636;
                border: 1px solid #238636;
            }
            QPushButton:disabled {
                background-color: #30363d;
                border: 1px solid #30363d;
                color: #6e7681;
            }
        """)
        self.runButton.clicked.connect(self._action_run)
        tb.addWidget(self.runButton)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")

        self._editor = CodeEditor()
        self._editor.setPlainText("")
        self._highlighter = SyntaxHigh(self._editor.document())
        splitter.addWidget(self._editor)

        self.setCentralWidget(splitter)

        sb = self.statusBar()
        sb.setContentsMargins(0, 0, 12, 0)
        sb.setStyleSheet(f"""
            QStatusBar {{
                background: {BG_CARD};
                color: {TEXT_MUTED};
                border-top: 1px solid {BORDER};
                font-size: 11px;
            }}
            QStatusBar::item {{
            border: none;
            }}
        """)

        self._status_indicator = QLabel("")
        self._status_indicator.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold;padding: 0px 12px")
        sb.addPermanentWidget(self._status_indicator)

        self._editor.textChanged.connect(self._on_text_changed)
        self._editor.cursorPositionChanged.connect(self._on_text_changed)
        self._on_text_changed()

    def _on_text_changed(self):
        cursor = self._editor.textCursor()
        self._status_indicator.setText(f"Ln {cursor.blockNumber()+1}, Col {cursor.positionInBlock()+1}")
        self._status_indicator.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold;width:100%;")

    def _action_run(self):
        from PySide6.QtWidgets import QMessageBox
        try:
            parser = TMParser()
            data = parser.parse(self._editor.toPlainText())
            parser.validate()
        except Exception as e:
            print(e)
            msg = QMessageBox(self)
            msg.setWindowTitle("Cannot Run")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("<b>Errors!</b>")
            msg.setInformativeText(str(e))
            msg.setStyleSheet(f"""
                QMessageBox {{
                    background: {BG_PANEL};
                }}
                QLabel {{
                    color: {TEXT_PRIMARY};
                    font-size: 12px;
                }}
                QPushButton {{
                    background: {BG_CARD};
                    color: {TEXT_PRIMARY};
                    border: 1px solid {BORDER};
                    border-radius: 4px;
                    padding: 4px 14px;
                }}
            """)
            msg.exec()
            return

        try:
            from executer import ExecutionDialog
            dlg = ExecutionDialog(data, self.tapeInput.text().strip() or "_", self)
            dlg.exec()
        except Exception as e:
            print(e)
            QMessageBox.critical(self, "Runtime Error", str(e))

    def _action_new(self): self._editor.setPlainText("")

    def _action_open(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Open TM File", "", "TM Files (*.tm);;All Files (*)")
        if path:
            with open(path, "r") as f:
                self._editor.setPlainText(f.read())
                self.fileName.setText(path)

    def _action_save(self):
        from PySide6.QtWidgets import QFileDialog
        if os.path.exists(self.fileName.text()):
            with open(self.fileName.text(), "w") as f:
                f.write(self._editor.toPlainText())
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save TM File", "", "TM Files (*.tm);;All Files (*)")
        if path:
            with open(path, "w") as f:
                f.write(self._editor.toPlainText())



def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Turing Machine Simulator")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(BG_PANEL))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base,            QColor(BG_DEEP))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text,            QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button,          QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(ACCENT_BLUE))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()