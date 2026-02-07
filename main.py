import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QListWidget, QListWidgetItem, QGroupBox, QPlainTextEdit,
    QMessageBox,
    QAbstractItemView
)

# -------------------------
# Safety: strip sensitive payment fields
# -------------------------
FORBIDDEN_KEY_PATTERNS = [
    r"^z$",
]

def is_forbidden_key(key: str) -> bool:
    k = (key or "").strip().lower()
    return any(re.search(p, k) for p in FORBIDDEN_KEY_PATTERNS)

def mono_font() -> QFont:
    f = QFont("Consolas")
    if not f.exactMatch():
        f = QFont("Courier New")
    return f

@dataclass
class ProfileData:
    raw: Dict[str, str]

    @staticmethod
    def from_json(path: str) -> "ProfileData":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON must be an object (key/value pairs).")
        sdata = {str(k): "" if v is None else str(v) for k, v in data.items()}
        return ProfileData(raw=sdata)

    def safe_items(self) -> List[Tuple[str, str]]:
        return [(k, v) for k, v in self.raw.items() if not is_forbidden_key(k)]

    def forbidden_items(self) -> List[Tuple[str, str]]:
        return [(k, v) for k, v in self.raw.items() if is_forbidden_key(k)]


class DraggableList(QListWidget):
    """List where each item can be dragged as plain text (value) and as JSON (key/value)."""

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return
        payload = item.data(Qt.UserRole) or {}
        key = payload.get("key", "")
        value = payload.get("value", "")

        mime = QMimeData()
        mime.setText(value)
        mime.setData(
            "application/x-profile-field",
            json.dumps({"key": key, "value": value}).encode("utf-8")
        )

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)


class DropPad(QPlainTextEdit):
    """Drop target that appends drops and copies dropped value to clipboard."""

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setAcceptDrops(True)
        self.setFont(mono_font())
        self.setPlaceholderText(
            "Drop here…\n\n"
            "• Dropped items are appended\n"
            "• Value is copied to clipboard"
        )

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasText() or md.hasFormat("application/x-profile-field"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        key = ""
        value = md.text()

        if md.hasFormat("application/x-profile-field"):
            try:
                payload = json.loads(bytes(md.data("application/x-profile-field")).decode("utf-8"))
                key = payload.get("key", "")
                value = payload.get("value", value)
            except Exception:
                pass

        if key:
            self.appendPlainText(f"{key}: {value}")
        else:
            self.appendPlainText(value)

        QApplication.clipboard().setText(value)
        event.acceptProposedAction()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Profile Drag & Drop (Simple)")
        self.resize(720, 520)

        self.profile: Optional[ProfileData] = None

        self.btn_load = QPushButton("Load JSON…")
        self.btn_load.clicked.connect(self.load_json)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_all)

        self.hint = QLabel(
            "Drag fields from the list and drop into the pad.\n"
            "Dropped value is copied to clipboard automatically."
        )
        self.hint.setWordWrap(True)

        self.safe_list = DraggableList()
        self.safe_list.setFont(mono_font())

        self.forbidden_list = QListWidget()
        self.forbidden_list.setFont(mono_font())
        self.forbidden_list.setEnabled(False)

        self.drop_pad = DropPad()

        top = QHBoxLayout()
        top.addWidget(self.btn_load)
        top.addWidget(self.btn_clear)
        top.addStretch(1)

        left_box = QGroupBox("Fields (draggable)")
        left_layout = QVBoxLayout(left_box)
        left_layout.addWidget(self.safe_list, 1)

        right_box = QGroupBox("Drop Pad")
        right_layout = QVBoxLayout(right_box)
        right_layout.addWidget(self.drop_pad, 1)

        warn_box = QGroupBox("Excluded (not draggable)")
        warn_layout = QVBoxLayout(warn_box)
        warn_layout.addWidget(QLabel("Payment-like keys are excluded (card number/CVV/expiry)."))
        warn_layout.addWidget(self.forbidden_list, 1)

        mid = QHBoxLayout()
        mid.addWidget(left_box, 2)
        mid.addWidget(right_box, 3)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.hint)
        layout.addLayout(mid, 1)
        layout.addWidget(warn_box, 1)

        # Preload sample (safe keys will show, forbidden keys will be excluded)
        self.populate_from_dict({
            "profile_name": "Billing",
            "billing_name": "Megan Young",
            "email": "",
            "phone": "9999999999",
            "address1": "10 Bass Dr",
            "address2": "",
            "city": "Succasunna",
            "state": "NJ",
            "zip": "07876",
            "country": "US",
            "name": "Megan Young",
            "card_number": "5424181632260720",
            "card_expiration": "11/29",
            "card_cvv": "976"
        })

    def clear_all(self):
        self.safe_list.clear()
        self.forbidden_list.clear()
        self.drop_pad.clear()

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load JSON", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            prof = ProfileData.from_json(path)
            self.populate_profile(prof)
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))

    def populate_profile(self, prof: ProfileData):
        self.profile = prof
        self.clear_all()

        for k, v in prof.safe_items():
            item = QListWidgetItem(f"{k}: {v}")
            item.setData(Qt.UserRole, {"key": k, "value": v})
            self.safe_list.addItem(item)

        for k, _v in prof.forbidden_items():
            self.forbidden_list.addItem(f"{k}: [excluded]")

    def populate_from_dict(self, d: Dict[str, str]):
        prof = ProfileData(raw={str(k): "" if v is None else str(v) for k, v in d.items()})
        self.populate_profile(prof)


def main():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
