import sys
from pathlib import Path

STYLE_TOKENS = {
    "dark_surface": "#0f1724",
    "dark_surface_alt": "#101927",
    "dark_border": "#2b3d58",
    "dark_text": "#d8e8ff",
    "light_surface": "#ffffff",
    "light_surface_alt": "#f4f7fb",
    "light_border": "#c9d6e8",
    "light_text": "#172033",
}

APP_FONT_PRIMARY = "Segoe UI"
APP_MONOSPACE_FONT_PRIMARY = "JetBrains Mono"
APP_FONT_STACK = '"Segoe UI", "Inter", "SF Pro Display", "Roboto", "Arial", sans-serif'
APP_MONOSPACE_FONT_STACK = '"JetBrains Mono", "Cascadia Code", "SF Mono", "Consolas", "Liberation Mono", monospace'


def app_font_primary(font_style="default"):
    return APP_MONOSPACE_FONT_PRIMARY if str(font_style or "").lower() == "monospace" else APP_FONT_PRIMARY


def app_font_stack(font_style="default"):
    return APP_MONOSPACE_FONT_STACK if str(font_style or "").lower() == "monospace" else APP_FONT_STACK


def _asset_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


def _asset_path(*parts: str) -> Path:
    return _asset_root().joinpath(*parts)


def scaled_font_px(value, zoom_percent=100, minimum=10):
    """Return a zoom-aware pixel size for final typography overrides."""
    try:
        scale = float(zoom_percent) / 100.0
    except (TypeError, ValueError):
        scale = 1.0
    return max(minimum, int(round(value * scale)))


APP_STYLESHEET = """
QWidget {
    background-color: #0f1117;
    color: #e8edf7;
    font-family: "Segoe UI", "Inter", "SF Pro Display", "Roboto", "Arial", sans-serif;
    font-size: 14px;
}

QWidget#Sidebar {
    background-color: #111827;
    border-right: 1px solid #222a38;
}

QWidget#MiddlePanel {
    background-color: #0f141d;
    border-right: 1px solid #222a38;
}

QWidget#RightPanel {
    background-color: #0f1117;
}

QLabel {
    font-size: 16px;
    background: transparent;
}

QLabel#SidebarTitle {
    color: #f8fafc;
    font-size: 20px;
    font-weight: 700;
}

QPushButton#SidebarTitleButton {
    background-color: transparent;
    border: none;
    padding: 4px 8px;
    text-align: left;
    color: #f8fafc;
    font-size: 20px;
    font-weight: 800;
}

QPushButton#SidebarTitleButton:hover {
    background-color: rgba(255, 255, 255, 0.06);
    border-radius: 10px;
}

QLabel#SectionCaption {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}

QWidget#SectionHeader {
    background-color: transparent;
    border: none;
}

QWidget#SectionHeader QLabel {
    background-color: transparent;
}

QPushButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    color: #dbe7f7;
}

QPushButton:hover {
    background-color: #1f2937;
    border: 1px solid #2f3a4d;
}

QPushButton:pressed {
    background-color: #2563eb;
    color: white;
}

QPushButton:disabled {
    color: #64748b;
    background-color: transparent;
}

QPushButton#IconButton {
    background-color: #1f2937;
    border: 1px solid #2f3a4d;
    border-radius: 10px;
    padding: 0px;
    text-align: center;
    font-size: 17px;
}

QPushButton#FileHeaderIconButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 0px;
    text-align: center;
}

QPushButton#FileHeaderIconButton:hover {
    background-color: #1f2937;
    border: 1px solid #2f3a4d;
}

QPushButton#FileHeaderIconButton:pressed {
    background-color: #2563eb;
    border: 1px solid #3b82f6;
}

QPushButton#ImageRotateButton {
    background-color: #172033;
    border: 1px solid #2a3448;
    border-radius: 9px;
    padding: 0px;
    font-size: 15px;
    text-align: center;
}

QPushButton#ImageRotateButton:hover {
    background-color: #1f2937;
    border: 1px solid #3b82f6;
}

QPushButton#ImageRotateButton:pressed {
    background-color: #2563eb;
    border: 1px solid #3b82f6;
}

QPushButton#SidebarLogoButton {
    background-color: transparent;
    border: none;
    border-radius: 10px;
    padding: 0px;
    text-align: center;
}

QPushButton#SidebarLogoButton:hover {
    background-color: #263449;
    border: none;
}

QPushButton#SidebarLogoButton:pressed {
    background-color: #1d4ed8;
    border: none;
}

QPushButton#SmallButton {
    background-color: #172033;
    border: 1px solid #2a3448;
    border-radius: 9px;
    padding: 7px 9px;
    font-size: 12px;
    text-align: center;
}

QCheckBox {
    color: #94a3b8;
    spacing: 8px;
    background: transparent;
}

QListWidget,
QTreeWidget {
    background-color: #111827;
    border: 1px solid #222a38;
    border-radius: 14px;
    padding: 8px;
    outline: none;
}

QListWidget#HistoryList {
    background-color: transparent;
    border: none;
    padding: 2px;
}

QListWidget::item,
QTreeWidget::item {
    padding: 8px;
    border-radius: 8px;
}

QListWidget::item:hover,
QTreeWidget::item:hover {
    background-color: #1f2937;
}

QListWidget::item:selected,
QTreeWidget::item:selected {
    background-color: #2563eb;
    color: white;
}

QFrame#HistoryPanel,
QFrame#ContentPanel,
QFrame#MetricCard {
    background-color: #141b2a;
    border: 1px solid #263244;
    border-radius: 16px;
}

QFrame#MetricCard {
    padding: 10px;
}

QLabel#MetricTitle {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 700;
}

QLabel#MetricValue {
    color: #f8fafc;
    font-size: 25px;
    font-weight: 800;
}

QLabel#PageTitle {
    color: #f8fafc;
    font-size: 30px;
    font-weight: 800;
}

QLabel#PageSubtitle {
    color: #94a3b8;
    font-size: 14px;
}

QTextEdit {
    background-color: #111827;
    border: 1px solid #263244;
    border-radius: 12px;
    padding: 12px;
    color: #e8edf7;
}

QTextEdit#PreviewText {
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    color: #dbe7f7;
    selection-background-color: #2563eb;
}

QLabel#ImagePreview {
    background-color: #0b1020;
    border: 1px solid #263244;
    border-radius: 14px;
}

QTableWidget {
    background-color: #141b2a;
    border: 1px solid #263244;
    border-radius: 14px;
    gridline-color: #263244;
    selection-background-color: #2563eb;
    alternate-background-color: #111827;
}

QTableWidget#DashboardTable {
    background-color: #141b2a;
}

QHeaderView::section {
    background-color: #1f2937;
    color: #dbe7f7;
    border: none;
    padding: 9px;
    font-weight: 700;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

# Additional interaction polish overrides.
APP_STYLESHEET += """
QFrame#ContentPanel:hover,
QFrame#MetricCard:hover,
QFrame#HistoryPanel:hover {
    border: 1px solid #3b82f6;
    background-color: #172033;
}

QLabel#CardTitle {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 800;
    background: transparent;
}

QLabel#CardBody {
    color: #cbd5e1;
    font-size: 14px;
    line-height: 1.45;
    background: transparent;
}

QTextEdit#CodePreview {
    background-color: #0b1020;
    border: 1px solid #263244;
    border-radius: 12px;
    padding: 12px;
    color: #dbeafe;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 13px;
    selection-background-color: #2563eb;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

QMenu {
    background-color: #111827;
    color: #e8edf7;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 8px;
}

QMenu::item {
    padding: 8px 28px 8px 12px;
    border-radius: 8px;
}

QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #263244;
    margin: 7px 6px;
}

QMenu::item:disabled {
    color: #64748b;
    background: transparent;
}

QToolTip {
    background-color: #111827;
    color: #e8edf7;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
}
"""

# Active sidebar navigation state.
APP_STYLESHEET += """
QPushButton[active="true"] {
    background-color: #2563eb;
    border: 1px solid #60a5fa;
    color: #ffffff;
    font-weight: 700;
}

QPushButton[active="true"]:hover {
    background-color: #1d4ed8;
    border: 1px solid #93c5fd;
}
"""


APP_STYLESHEET += """
/* Course dashboard simplified card layout */
QLabel#SectionTitle {
    color: #f8fafc;
    font-size: 19px;
    font-weight: 850;
    background: transparent;
}

QLabel#SectionSubtext {
    color: #94a3b8;
    font-size: 13px;
    background: transparent;
}

QFrame#DashboardItemCard {
    background-color: #111827;
    border: 1px solid #263244;
    border-radius: 14px;
}

QFrame#DashboardItemCard:hover {
    background-color: #172033;
    border: 1px solid #3b82f6;
}

QLabel#CardMeta {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 650;
    background: transparent;
}

QLabel#CardHint {
    color: #64748b;
    font-size: 11px;
    background: transparent;
}

QLabel#StatusPill {
    color: #bfdbfe;
    background-color: #1e3a8a;
    border: 1px solid #2563eb;
    border-radius: 11px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 800;
    min-width: 70px;
}

QLabel#DuePill {
    color: #dcfce7;
    background-color: #14532d;
    border: 1px solid #22c55e;
    border-radius: 11px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 800;
    min-width: 84px;
}

QLabel#DuePillSafe {
    color: #dcfce7;
    background-color: #14532d;
    border: 1px solid #22c55e;
    border-radius: 11px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 800;
    min-width: 84px;
}

QLabel#DuePillSoon {
    color: #fef3c7;
    background-color: #78350f;
    border: 1px solid #f59e0b;
    border-radius: 11px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 800;
    min-width: 84px;
}

QLabel#DuePillUrgent {
    color: #fee2e2;
    background-color: #7f1d1d;
    border: 1px solid #ef4444;
    border-radius: 11px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 800;
    min-width: 84px;
}

QLabel#DuePillCompleted,
QLabel#DuePillNone {
    color: #e2e8f0;
    background-color: #334155;
    border: 1px solid #64748b;
    border-radius: 11px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 800;
    min-width: 84px;
}

"""

APP_STYLESHEET += """
/* Assignment dashboard refresh */
QFrame#AssignmentInfoCard {
    background-color: #111827;
    border: 1px solid #263244;
    border-radius: 16px;
}

QFrame#AssignmentInfoCard:hover {
    background-color: #172033;
    border: 1px solid #3b82f6;
}

QLabel#AssignmentInfoValue {
    color: #f8fafc;
    font-size: 24px;
    font-weight: 900;
    background: transparent;
}

QFrame#TodoCard,
QFrame#TodoCardDone,
QFrame#TodoEmptyState {
    background-color: #0f172a;
    border: 1px solid #263244;
    border-radius: 14px;
}

QFrame#TodoCardDone {
    background-color: #111827;
    border: 1px solid #243044;
}

QFrame#TodoEmptyState {
    background-color: #111827;
    border-style: dashed;
}

QFrame#TodoCard:hover,
QFrame#TodoCardDone:hover,
QFrame#TodoEmptyState:hover {
    background-color: #172033;
    border: 1px solid #3b82f6;
}

QLabel#TodoTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 750;
    background: transparent;
}

QLabel#TodoTitleDone {
    color: #94a3b8;
    font-size: 14px;
    font-weight: 650;
    background: transparent;
    text-decoration: line-through;
}

QLabel#TodoSummary {
    color: #cbd5e1;
    font-size: 12px;
    font-weight: 750;
    background: transparent;
}

QLabel#TodoEmptyIcon {
    background-color: #172033;
    border: 1px solid #334155;
    border-radius: 17px;
}

QLabel#TodoEmptyTitle {
    color: #f8fafc;
    font-size: 14px;
    font-weight: 800;
    background: transparent;
}

QLabel#TodoEmptyBody {
    color: #94a3b8;
    font-size: 13px;
    background: transparent;
}

QProgressBar#TodoProgressBar {
    background-color: #0b1220;
    border: 1px solid #1f2a3d;
    border-radius: 4px;
}

QProgressBar#TodoProgressBar::chunk {
    background-color: #22c55e;
    border-radius: 4px;
}

QCheckBox#TodoCheckbox {
    spacing: 0px;
    padding: 0px;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
}

QCheckBox#TodoCheckbox::indicator {
    width: 18px;
    height: 18px;
    margin-left: 3px;
    margin-top: 3px;
}

QPushButton#DangerSmallButton {
    background-color: #3f1d1d;
    border: 1px solid #7f1d1d;
    border-radius: 9px;
    padding: 6px 10px;
    color: #fecaca;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#DangerSmallButton:hover {
    background-color: #7f1d1d;
    border: 1px solid #f87171;
    color: #ffffff;
}

QPushButton#DangerIconButton {
    background-color: #3f1d1d;
    border: 1px solid #7f1d1d;
    border-radius: 9px;
    padding: 6px;
    color: #fecaca;
}

QPushButton#DangerIconButton:hover {
    background-color: #7f1d1d;
    border: 1px solid #f87171;
    color: #ffffff;
}
"""

# Premium readability and structured preview overrides.
APP_STYLESHEET += """
QWidget {
    background-color: #11151d;
    color: #e8ecf3;
    font-family: "Inter", "Segoe UI", "SF Pro Display", "Roboto", sans-serif;
    font-size: 14px;
}

QLabel {
    color: #e8ecf3;
    background: transparent;
}

QLabel#PageTitle {
    color: #ffffff;
    font-size: 28px;
    font-weight: 800;
}

QLabel#PageSubtitle {
    color: #9aa6b8;
    font-size: 14px;
    font-weight: 500;
}

QLabel#CardTitle {
    color: #f7faff;
    font-size: 15px;
    font-weight: 750;
}

QLabel#CardBody {
    color: #c9d3e3;
    font-size: 14px;
    line-height: 1.5;
}

QLabel#MutedText {
    color: #98a2b3;
    font-size: 13px;
}

QLabel#MetaText,
QLabel#DetailKey {
    color: #8491a5;
    font-size: 12px;
    font-weight: 650;
}

QLabel#DetailValue {
    color: #dce5f4;
    font-size: 13px;
    font-weight: 500;
}

QFrame#PreviewCard,
QFrame#DetailsCard,
QFrame#ContentPanel,
QFrame#DashboardCard,
QFrame#DashboardItemCard,
QFrame#AssignmentInfoCard,
QFrame#TodoCard,
QFrame#TodoCardDone,
QFrame#TodoEmptyState {
    background-color: #1a202c;
    border: 1px solid #283244;
    border-radius: 18px;
}

QFrame#PreviewCard:hover,
QFrame#DetailsCard:hover,
QFrame#ContentPanel:hover,
QFrame#DashboardCard:hover,
QFrame#DashboardItemCard:hover,
QFrame#AssignmentInfoCard:hover,
QFrame#TodoCard:hover,
QFrame#TodoCardDone:hover,
QFrame#TodoEmptyState:hover {
    background-color: #1d2634;
    border: 1px solid #3b82f6;
}

QTextEdit#CodePreview,
QPlainTextEdit#CodePreview {
    background-color: #111827;
    border: 1px solid #263244;
    border-radius: 14px;
    padding: 14px;
    color: #dbeafe;
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
    selection-background-color: #2563eb;
}

QLabel#ImagePreview {
    background-color: #111827;
    border: 1px solid #263244;
    border-radius: 16px;
    padding: 12px;
}

QWidget#SidebarButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
}

QWidget#SidebarButton:hover {
    background-color: #202938;
    border: 1px solid #303b50;
}

QLabel#SidebarButtonIcon {
    background-color: #172033;
    border: 1px solid #2a3448;
    border-radius: 8px;
    padding: 0px;
}

QLabel#SidebarButtonText {
    color: #d7e0ee;
    font-size: 20px;
    font-weight: 650;
}

QWidget#SidebarButton:hover QLabel#SidebarButtonText {
    color: #ffffff;
}

QWidget#SidebarButton[active="true"] {
    background-color: #2563eb;
    border: 1px solid #60a5fa;
}

QWidget#SidebarButton[active="true"] QLabel#SidebarButtonIcon {
    background-color: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.24);
}

QWidget#SidebarButton[active="true"] QLabel#SidebarButtonText {
    color: #ffffff;
    font-weight: 750;
}

QListWidget::item,
QTreeWidget::item {
    padding: 9px;
    border-radius: 9px;
}

QMenu::item:disabled {
    color: #8491a5;
    font-weight: 750;
}
"""

APP_STYLESHEET += """
/* Browser list cards */
QListWidget::item {
    padding: 0px;
    margin: 0px;
    border: none;
}

QFrame#BrowserItemCard {
    background-color: #141b2a;
    border: 1px solid #243042;
    border-radius: 16px;
}

QFrame#BrowserItemCard:hover {
    background-color: #182132;
    border: 1px solid #35507a;
}

QFrame#BrowserItemCard[selected="true"] {
    background-color: #1c2950;
    border: 1px solid #4f84ff;
}

QFrame#BrowserItemCard[activeContext="true"] {
    border: 1px solid #3968cf;
}

QLabel#BrowserItemIcon {
    background-color: #111827;
    border: 1px solid #293548;
    border-radius: 10px;
    padding: 6px;
}

QLabel#BrowserItemTitle {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 800;
}

QLabel#BrowserItemSubtitle {
    color: #c9d6ea;
    font-size: 13px;
    font-weight: 650;
}

QLabel#BrowserItemMeta {
    color: #8ea1bd;
    font-size: 12px;
    font-weight: 600;
}

QLabel#StatusBadge {
    background-color: #2d4f9e;
    color: #f8fbff;
    border: 1px solid #5d8cff;
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 800;
}

QLabel#CardBody {
    color: #d3deef;
    font-size: 14px;
    font-weight: 500;
}

QLabel#DetailKey {
    color: #90a1b8;
    font-size: 12px;
    font-weight: 700;
    padding-right: 8px;
}

QLabel#DetailValue {
    color: #edf3ff;
    font-size: 13px;
    font-weight: 500;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

"""


APP_STYLESHEET += """
/* Dialogs and popup windows */
QDialog,
QMessageBox,
QInputDialog,
QFileDialog {
    background-color: #111827;
    color: #e8edf7;
    font-family: "Inter", "Segoe UI", "SF Pro Display", "Roboto", sans-serif;
}

QDialog QLabel,
QMessageBox QLabel,
QInputDialog QLabel,
QFileDialog QLabel {
    color: #dbe7f7;
    font-size: 14px;
}

QLineEdit,
QPlainTextEdit,
QTextEdit {
    selection-background-color: #2563eb;
}

QLineEdit {
    background-color: #0f141d;
    border: 1px solid #283244;
    border-radius: 10px;
    padding: 9px 11px;
    color: #edf3ff;
}

QLineEdit:focus {
    border: 1px solid #4f84ff;
}

QDialog QPushButton,
QMessageBox QPushButton,
QInputDialog QPushButton,
QFileDialog QPushButton {
    background-color: #172033;
    border: 1px solid #2f3a4d;
    border-radius: 10px;
    padding: 8px 14px;
    color: #e8edf7;
    min-width: 76px;
    text-align: center;
}

QDialog QPushButton:hover,
QMessageBox QPushButton:hover,
QInputDialog QPushButton:hover,
QFileDialog QPushButton:hover {
    background-color: #24314a;
    border: 1px solid #4f84ff;
}

/* File explorer polish */
QTreeWidget {
    background-color: #111827;
    border: 1px solid #243042;
    border-radius: 16px;
    padding: 10px;
    alternate-background-color: #121b2a;
    show-decoration-selected: 1;
}

QTreeWidget::item {
    min-height: 30px;
    padding: 8px 10px;
    margin: 2px 0px;
    border: 1px solid transparent;
    border-radius: 10px;
    color: #dbe7f7;
}

QTreeWidget::item:hover {
    background-color: #192233;
    border: 1px solid #2f4365;
    color: #ffffff;
}

QTreeWidget::item:selected {
    background-color: #1f3b77;
    border: 1px solid #5d8cff;
    color: #ffffff;
}

/* Stronger card text wrapping/readability */
QLabel#CardBody,
QLabel#DetailValue,
QLabel#BrowserItemSubtitle,
QLabel#BrowserItemMeta {
    line-height: 1.45;
}
"""


APP_STYLESHEET += """
/* File explorer context and rubber-band selection.
   Branch/expand indicators intentionally use the native Qt style.
   Do not set SVG images here: QSS image paths are fragile on Windows paths with spaces. */
QLabel#ScopeContextBar {
    color: #9fb0c8;
    font-size: 12px;
    font-weight: 600;
    background-color: #111827;
    border: 1px solid #243042;
    border-radius: 12px;
    padding: 9px 11px;
}

QRubberBand {
    border: 1px solid #60a5fa;
    background-color: rgba(96, 165, 250, 48);
}
"""

APP_STYLESHEET += """
/* Cohesive tree row selection.
   Do not style QTreeWidget::branch here; native arrows must stay native.
   Instead, make the item highlight visually merge with Qt's branch highlight. */
QTreeWidget::item {
    min-height: 30px;
    padding: 7px 10px;
    margin: 0px;
    border: none;
    border-radius: 0px;
    color: #dbe7f7;
}

QTreeWidget::item:hover {
    background-color: #192233;
    border: none;
    border-radius: 0px;
    color: #ffffff;
}

QTreeWidget::item:selected {
    background-color: #1f3b77;
    border: none;
    border-radius: 0px;
    color: #ffffff;
}
"""

APP_STYLESHEET += """
QLabel#SidebarUserChip {
    color: #aab8ce;
    background-color: #0f172a;
    border: 1px solid #243042;
    border-radius: 12px;
    padding: 8px 10px;
    font-size: 12px;
    font-weight: 650;
    line-height: 1.35;
}
"""



APP_STYLESHEET += """
/* Resizable content splitter */
QSplitter#ContentSplitter {
    background-color: #0f1117;
}

QSplitter#ContentSplitter::handle {
    background-color: transparent;
    border: none;
    margin: 0px;
}

QSplitter#ContentSplitter::handle:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent,
        stop:0.44 transparent,
        stop:0.45 #60a5fa,
        stop:0.55 #60a5fa,
        stop:0.56 transparent,
        stop:1 transparent
    );
    border: none;
}

/* Canvas sync progress popup */
QProgressDialog#CanvasSyncProgress {
    background-color: #111827;
    color: #e8edf7;
    border: 1px solid #334155;
    border-radius: 18px;
}

QProgressDialog#CanvasSyncProgress QLabel {
    color: #dbeafe;
    font-size: 14px;
    font-weight: 650;
    padding: 8px 2px;
}

QProgressDialog#CanvasSyncProgress QProgressBar {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 9px;
    min-height: 18px;
    max-height: 18px;
    text-align: center;
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
}

QProgressDialog#CanvasSyncProgress QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 8px;
    margin: 1px;
}
"""

APP_STYLESHEET += """
/* Canvas course preference dialogs */
QListWidget#CoursePreferenceList {
    background-color: #0f172a;
    border: 1px solid #263244;
    border-radius: 14px;
    padding: 10px;
}

QListWidget#CoursePreferenceList::item {
    padding: 6px;
    border-radius: 12px;
}

QListWidget#CoursePreferenceList::item:hover {
    background-color: #172033;
}
"""

APP_STYLESHEET += """
/* Compact section-level action bar used above the Courses list. */
QFrame#SectionActionBar {
    background-color: #121a2a;
    border: 1px solid #243042;
    border-radius: 14px;
}

QPushButton#ToolbarButton {
    background-color: #172033;
    border: 1px solid #2a3b58;
    border-radius: 9px;
    padding: 7px 6px;
    color: #e8ecf3;
    font-size: 11px;
    font-weight: 700;
    text-align: center;
}

QPushButton#ToolbarButton:hover {
    background-color: #1c2950;
    border: 1px solid #5d8cff;
    color: #ffffff;
}

QPushButton#ToolbarButton:disabled {
    background-color: #111827;
    border: 1px solid #1f2937;
    color: #64748b;
}
"""


def _adjust_hex(hex_color: str, factor: float) -> str:
    hex_color = (hex_color or "#2563eb").strip()
    if not hex_color.startswith("#") or len(hex_color) not in {4, 7, 9}:
        hex_color = "#2563eb"
    if len(hex_color) == 4:
        hex_color = "#" + "".join(ch * 2 for ch in hex_color[1:])
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    if factor >= 1:
        r = int(r + (255 - r) * (factor - 1))
        g = int(g + (255 - g) * (factor - 1))
        b = int(b + (255 - b) * (factor - 1))
    else:
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _qss_url(path: Path) -> str:
    return path.resolve().as_posix()


def build_zoom_stylesheet(zoom_percent=100):
    """Return the final zoom layer shared by the main window and child windows."""
    try:
        scale = int(zoom_percent) / 100.0
    except (TypeError, ValueError):
        scale = 1.0

    def px(value):
        return max(8, int(round(value * scale)))

    return f"""
/* Runtime UI zoom layer */
QWidget {{
    font-size: {px(14)}px;
}}

QLabel {{
    font-size: {px(16)}px;
}}

QPushButton,
QLineEdit,
QComboBox,
QCheckBox,
QMenu {{
    font-size: {px(14)}px;
}}

QMenu::item {{
    font-size: {px(14)}px;
    min-height: {px(30)}px;
}}

QTextEdit,
QPlainTextEdit,
QTextEdit#PreviewText,
QTextEdit#RichDocumentPreview,
QTextEdit#LibraryDetails {{
    font-size: {px(16)}px;
}}

QLabel#DetailValue,
QLabel#CardBody,
QLabel#SectionSubtext,
QLabel#PageSubtitle {{
    font-size: {px(15)}px;
}}

QLabel#PageTitle {{
    font-size: {px(30)}px;
}}

QLabel#SidebarTitle {{
    font-size: {px(20)}px;
}}

QLabel#LibraryTitle {{
    font-size: {px(22)}px;
}}

QLabel#LibrarySubtitle {{
    font-size: {px(13)}px;
}}

QLabel#DashboardProgressValue {{
    font-size: {px(46)}px;
}}

QProgressBar#DashboardProgressBar {{
    min-height: {px(12)}px;
    max-height: {px(12)}px;
}}

QTreeWidget#ResourceTree::item,
QTreeWidget#LibraryTree::item {{
    min-height: {px(42)}px;
    font-size: {px(15)}px;
}}

QTreeWidget#ResourceTree,
QTreeWidget#LibraryTree {{
    padding: {px(12)}px;
}}

QListWidget::item {{
    min-height: {px(34)}px;
}}

QFrame#AssignmentListRow QLabel#CardTitle {{
    font-size: {px(16)}px;
}}

QFrame#AssignmentListRow QLabel#CardMeta {{
    font-size: {px(13)}px;
}}

QFrame#AssignmentListRow QLabel#DuePill,
QFrame#AssignmentListRow QLabel#DuePillSafe,
QFrame#AssignmentListRow QLabel#DuePillSoon,
QFrame#AssignmentListRow QLabel#DuePillUrgent,
QFrame#AssignmentListRow QLabel#DuePillCompleted,
QFrame#AssignmentListRow QLabel#DuePillNone {{
    font-size: {px(11)}px;
    padding: {px(5)}px {px(13)}px;
    min-width: {px(90)}px;
}}

QPushButton#AssignmentRowButton {{
    font-size: {px(12)}px;
    padding: {px(7)}px {px(11)}px;
}}
"""


def build_typography_normalization_styles(zoom_percent=100, font_style="default"):
    """Final, zoom-aware typography pass for consistent readable text."""
    base = scaled_font_px(17, zoom_percent)
    secondary = scaled_font_px(16, zoom_percent)
    small = scaled_font_px(15, zoom_percent)
    tiny = scaled_font_px(14, zoom_percent)
    body = scaled_font_px(18, zoom_percent)
    title = scaled_font_px(20, zoom_percent)
    page_title = scaled_font_px(34, zoom_percent)
    sidebar_title = scaled_font_px(20, zoom_percent)
    sidebar_button = scaled_font_px(20, zoom_percent)
    sidebar_user = scaled_font_px(17, zoom_percent)
    sidebar_caption = scaled_font_px(15, zoom_percent)
    sidebar_history = scaled_font_px(16, zoom_percent)
    metric = scaled_font_px(50, zoom_percent)
    code = scaled_font_px(16, zoom_percent)
    font_stack = app_font_stack(font_style)

    return f"""
/* Final typography normalization: one readable app font, scaled with UI zoom. */
QWidget,
QDialog,
QMessageBox,
QInputDialog,
QFileDialog,
QMenu,
QToolTip {{
    font-family: {font_stack};
    font-size: {base}px;
}}

QLabel,
QPushButton,
QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QCheckBox,
QRadioButton,
QListWidget,
QTreeWidget,
QTableWidget,
QHeaderView::section,
QMenu::item {{
    font-family: {font_stack};
    font-size: {base}px;
}}

QLabel#PageTitle {{
    font-size: {page_title}px;
}}

QLabel#SidebarTitle,
QPushButton#SidebarTitleButton {{
    font-size: {sidebar_title}px;
}}

QWidget#SidebarButton {{
    min-height: {scaled_font_px(40, zoom_percent)}px;
}}

QLabel#SidebarButtonText {{
    font-size: {sidebar_button}px;
    font-weight: 650;
}}

QLabel#SidebarButtonIcon {{
    min-width: {scaled_font_px(28, zoom_percent)}px;
    max-width: {scaled_font_px(28, zoom_percent)}px;
    min-height: {scaled_font_px(28, zoom_percent)}px;
    max-height: {scaled_font_px(28, zoom_percent)}px;
}}

QLabel#SidebarProfileSchool {{
    font-size: {small}px;
}}

QLabel#SidebarProfileBadge {{
    font-size: {tiny}px;
}}

QLabel#SidebarUserChip {{
    font-size: {sidebar_user}px;
    padding: {scaled_font_px(10, zoom_percent)}px {scaled_font_px(12, zoom_percent)}px;
}}

QFrame#HistoryPanel QLabel#SectionCaption {{
    font-size: {sidebar_caption}px;
}}

QListWidget#HistoryList,
QListWidget#HistoryList::item,
QFrame#HistoryPanel QPushButton#SmallButton,
QFrame#HistoryPanel QCheckBox {{
    font-size: {sidebar_history}px;
}}

QLabel#LibraryTitle,
QLabel#SectionTitle,
QLabel#CardTitle,
QLabel#BrowserItemTitle,
QLabel#TodoTitle,
QLabel#DialogTitle {{
    font-size: {title}px;
}}

QLabel#CardBody,
QLabel#DetailValue,
QLabel#BrowserItemSubtitle,
QLabel#PageSubtitle,
QLabel#SectionSubtext,
QLabel#DialogBody,
QLabel#DialogStatus {{
    font-size: {body}px;
}}

QLabel#LibrarySubtitle,
QLabel#MutedText,
QLabel#MetaText,
QLabel#CardMeta,
QLabel#BrowserItemMeta,
QLabel#DetailKey,
QLabel#MetricTitle,
QLabel#FieldLabel,
QLabel#SliderValue,
QLabel#DialogSubtitle,
QLabel#FieldHint,
QLabel#DialogDetail {{
    font-size: {small}px;
}}

QLabel#SectionCaption,
QLabel#CardHint,
QLabel#StatusPill,
QLabel#StatusBadge,
QLabel#DuePill,
QLabel#DuePillSafe,
QLabel#DuePillSoon,
QLabel#DuePillUrgent,
QLabel#DuePillCompleted,
QLabel#DuePillNone {{
    font-size: {tiny}px;
}}

QTextEdit,
QPlainTextEdit,
QTextEdit#PreviewText,
QTextEdit#RichDocumentPreview,
QTextEdit#LibraryDetails {{
    font-family: {font_stack};
    font-size: {body}px;
}}

QTextEdit#CodePreview,
QPlainTextEdit#CodePreview {{
    font-family: "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: {code}px;
}}

QTreeWidget#ResourceTree::item,
QTreeWidget#LibraryTree::item {{
    font-size: {base}px;
}}

QFrame#AssignmentListRow QLabel#CardTitle {{
    font-size: {title}px;
}}

QFrame#AssignmentListRow QLabel#CardMeta,
QLabel#AssignmentDueDate,
QPushButton#AssignmentRowButton {{
    font-size: {secondary}px;
}}

QLabel#DashboardProgressValue,
QLabel#MetricValue {{
    font-size: {metric}px;
}}
"""


def build_context_menu_styles(theme="dark", accent="#2563eb"):
    """Return the canonical app context-menu style layer."""
    accent_dark = _adjust_hex(accent, 0.72)
    is_light = str(theme).lower() == "light"

    if is_light:
        menu_bg = STYLE_TOKENS["light_surface"]
        menu_text = "#1e3a5f"
        menu_border = STYLE_TOKENS["light_border"]
        disabled = "#8a98aa"
        separator = "#dbe3ef"
        quick_bg = "rgba(255, 255, 255, 0.98)"
        quick_hover = "#e7efff"
    else:
        menu_bg = "#0d1625"
        menu_text = "#cfe2ff"
        menu_border = "#38547a"
        disabled = "#71819a"
        separator = "#2b3a52"
        quick_bg = "rgba(13, 22, 37, 0.98)"
        quick_hover = "#1f3b77"

    return f"""
/* Canonical context menus */
QMenu {{
    background-color: {menu_bg};
    color: {menu_text};
    border: 1px solid {menu_border};
    border-radius: 14px;
    padding: 8px;
    icon-size: 22px;
    font-size: 14px;
    font-weight: 700;
}}

QMenu::item {{
    background-color: transparent;
    color: {menu_text};
    min-height: 30px;
    padding: 9px 44px 9px 42px;
    margin: 2px 3px;
    border-radius: 9px;
}}

QMenu::item:selected {{
    background-color: {accent_dark};
    color: #ffffff;
}}

QMenu::item:disabled {{
    color: {disabled};
    background-color: transparent;
}}

QMenu::separator {{
    height: 1px;
    background-color: {separator};
    margin: 7px 8px;
}}

QMenu::icon {{
    padding-left: 10px;
    padding-right: 12px;
}}

QMenu::right-arrow {{
    width: 11px;
    height: 11px;
    padding-right: 10px;
}}

QFrame#ContextQuickBar {{
    background-color: {quick_bg};
    border: 1px solid {menu_border};
    border-radius: 11px;
}}

QToolButton#ContextQuickButton {{
    background-color: transparent;
    border: none;
    border-radius: 9px;
    padding: 7px;
    min-width: 36px;
    min-height: 36px;
    max-width: 40px;
    max-height: 40px;
}}

QToolButton#ContextQuickButton:hover {{
    background-color: {quick_hover};
}}

QToolButton#ContextQuickButton:pressed {{
    background-color: {accent_dark};
}}
"""


def build_tree_styles(theme="dark", accent="#2563eb"):
    """Return the canonical main explorer and Resource Library tree style."""
    accent_dark = _adjust_hex(accent, 0.72)
    accent_hover = _adjust_hex(accent, 0.94)
    is_light = str(theme).lower() == "light"

    if is_light:
        bg = STYLE_TOKENS["light_surface"]
        border = STYLE_TOKENS["light_border"]
        text = "#1f3b58"
        hover_bg = "#edf4ff"
        hover_text = "#0f2440"
    else:
        bg = STYLE_TOKENS["dark_surface"]
        border = STYLE_TOKENS["dark_border"]
        text = STYLE_TOKENS["dark_text"]
        hover_bg = "#1a2940"
        hover_text = "#f4f9ff"

    return f"""
/* Canonical file explorer and Resource Library trees */
QTreeWidget#ResourceTree,
QTreeWidget#LibraryTree {{
    background-color: {bg};
    border: 1px solid {border};
    border-radius: 16px;
    padding: 12px;
    show-decoration-selected: 1;
}}

QTreeWidget#ResourceTree::item,
QTreeWidget#LibraryTree::item {{
    min-height: 42px;
    padding: 10px 12px;
    color: {text};
    font-size: 15px;
    font-weight: 650;
    border: none;
}}

QTreeWidget#ResourceTree::item:hover,
QTreeWidget#LibraryTree::item:hover {{
    background-color: {hover_bg};
    color: {hover_text};
    border: none;
}}

QTreeWidget#ResourceTree::item:selected,
QTreeWidget#ResourceTree::item:selected:active,
QTreeWidget#ResourceTree::item:selected:!active,
QTreeWidget#LibraryTree::item:selected,
QTreeWidget#LibraryTree::item:selected:active,
QTreeWidget#LibraryTree::item:selected:!active {{
    background-color: {accent_dark};
    color: #ffffff;
    border: none;
}}

QTreeWidget#ResourceTree::item:selected:hover,
QTreeWidget#LibraryTree::item:selected:hover {{
    background-color: {accent_hover};
}}

QTreeWidget#ResourceTree::branch,
QTreeWidget#LibraryTree::branch,
QTreeWidget#ResourceTree::branch:hover,
QTreeWidget#LibraryTree::branch:hover,
QTreeWidget#ResourceTree::branch:selected,
QTreeWidget#LibraryTree::branch:selected {{
    background: transparent;
    border: none;
}}
"""


def build_assignment_row_styles(theme="dark", accent="#2563eb"):
    """Return the shared assignment row/list-card style."""
    accent_dark = _adjust_hex(accent, 0.72)
    is_light = str(theme).lower() == "light"

    if is_light:
        bg = STYLE_TOKENS["light_surface"]
        hover_bg = "#f0f6ff"
        border = STYLE_TOKENS["light_border"]
        title = "#0f2440"
        meta = "#4f647d"
        button_bg = "#f4f7fb"
        button_border = "#c9d6e8"
        button_text = "#18324f"
    else:
        bg = STYLE_TOKENS["dark_surface_alt"]
        hover_bg = "#142033"
        border = "#26364e"
        title = "#f8fbff"
        meta = "#aac0dc"
        button_bg = "#142033"
        button_border = "#2b3f5e"
        button_text = "#e7f0ff"

    return f"""
/* Canonical assignment row/list cards */
QFrame#AssignmentListRow {{
    background-color: {bg};
    border: 1px solid {border};
    border-radius: 8px;
}}

QFrame#AssignmentListRow:hover {{
    background-color: {hover_bg};
    border: 1px solid {_adjust_hex(accent, 1.12)};
}}

QFrame#AssignmentListRow QLabel#CardTitle {{
    color: {title};
    font-size: 16px;
    font-weight: 800;
}}

QFrame#AssignmentListRow QLabel#CardMeta {{
    color: {meta};
    font-size: 13px;
    font-weight: 600;
}}

QLabel#AssignmentDueDate {{
    color: {title};
    font-size: 14px;
    font-weight: 750;
}}

QFrame#AssignmentListRow QLabel#DuePill,
QFrame#AssignmentListRow QLabel#DuePillSafe,
QFrame#AssignmentListRow QLabel#DuePillSoon,
QFrame#AssignmentListRow QLabel#DuePillUrgent,
QFrame#AssignmentListRow QLabel#DuePillCompleted,
QFrame#AssignmentListRow QLabel#DuePillNone {{
    border-radius: 11px;
    padding: 5px 13px;
    min-width: 90px;
    font-size: 11px;
    font-weight: 800;
}}

QPushButton#AssignmentRowButton {{
    background-color: {button_bg};
    border: 1px solid {button_border};
    border-radius: 9px;
    color: {button_text};
    padding: 7px 11px;
    min-width: 0px;
    font-size: 12px;
    font-weight: 650;
    text-align: center;
}}

QPushButton#AssignmentRowButton:hover {{
    background-color: {accent_dark};
    border: 1px solid {_adjust_hex(accent, 1.2)};
    color: #ffffff;
}}
"""


def build_preview_readability_styles(theme="dark"):
    """Return readable preview/detail text styles shared by app and library."""
    is_light = str(theme).lower() == "light"
    if is_light:
        bg = "#ffffff"
        border = STYLE_TOKENS["light_border"]
        text = "#172033"
    else:
        bg = "#0b1220"
        border = "#263244"
        text = "#dbeafe"

    return f"""
/* Canonical preview/detail readability */
QTextEdit#RichDocumentPreview,
QTextEdit#LibraryDetails {{
    background-color: {bg};
    border: 1px solid {border};
    border-radius: 16px;
    padding: 16px;
    color: {text};
    font-family: "Inter", "Segoe UI", "SF Pro Display", sans-serif;
    font-size: 14px;
    selection-background-color: #2563eb;
}}

QPdfView#PdfPreview,
QVideoWidget#MediaPreview {{
    background-color: {bg};
    border: 1px solid {border};
    border-radius: 16px;
}}

QSlider#MediaSlider::groove:horizontal,
QSlider#MediaVolume::groove:horizontal {{
    height: 8px;
    border-radius: 4px;
    background-color: {"#d7deea" if is_light else "#263244"};
}}

QSlider#MediaSlider,
QSlider#MediaVolume {{
    min-height: 38px;
    padding-left: 12px;
    padding-right: 12px;
}}

QSlider#MediaSlider::handle:horizontal,
QSlider#MediaVolume::handle:horizontal {{
    width: 20px;
    height: 20px;
    margin: -6px 0;
    border-radius: 10px;
    background-color: #2563eb;
}}

QScrollArea,
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
"""


def build_component_override_styles(theme="dark", accent="#2563eb"):
    """Return the final named component override sections."""
    return (
        build_context_menu_styles(theme, accent)
        + build_tree_styles(theme, accent)
        + build_assignment_row_styles(theme, accent)
        + build_preview_readability_styles(theme)
    )


def build_app_stylesheet(theme="dark", accent="#2563eb", zoom_percent=100, font_style="default"):
    """Return the app stylesheet with theme/accent overrides applied.

    The base QSS is dark-first because that was the original UI. The dynamic
    layer is appended last and intentionally restyles every major surface so
    light mode is complete rather than a partial colour inversion.
    """
    accent = accent or "#2563eb"
    accent_hover = _adjust_hex(accent, 1.22)
    accent_dark = _adjust_hex(accent, 0.72)
    check_icon = _qss_url(_asset_path("icons", "check.svg"))

    dynamic = f"""
/* Dynamic theme/accent layer */
QPushButton[active="true"],
QPushButton#SidebarButton[active="true"],
QWidget#SidebarButton[active="true"],
QLabel#StatusBadge {{
    background-color: {accent};
    border: 1px solid {accent_hover};
    color: #ffffff;
}}

QPushButton[active="true"]:hover,
QPushButton#SidebarButton[active="true"]:hover,
QWidget#SidebarButton[active="true"]:hover,
QPushButton#ToolbarButton:hover,
QPushButton#SmallButton:hover,
QPushButton#ImageRotateButton:hover,
QPushButton#IconButton:hover {{
    background-color: {accent_dark};
    border: 1px solid {accent_hover};
}}

QPushButton#FileHeaderIconButton:pressed,
QPushButton#ImageRotateButton:pressed {{
    background-color: {accent};
    border: 1px solid {accent_hover};
    color: #ffffff;
}}

QTreeWidget::item:selected,
QListWidget::item:selected {{
    background-color: {accent_dark};
    color: #ffffff;
}}

QMenu::item:selected {{
    background-color: {accent};
    color: #ffffff;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {accent_hover};
}}

QCheckBox {{
    color: #dbe7f7;
    spacing: 10px;
    background: transparent;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid #52627a;
    background-color: #0f172a;
}}

QCheckBox::indicator:hover {{
    border: 1px solid {accent_hover};
    background-color: #172033;
}}

QCheckBox::indicator:checked {{
    background-color: {accent};
    border: 1px solid {accent_hover};
    image: url("{check_icon}");
}}

QCheckBox::indicator:disabled {{
    background-color: #111827;
    border: 1px solid #263244;
}}

QMenu {{
    border-radius: 16px;
    padding: 9px;
}}

QMenu::item {{
    padding: 9px 30px 9px 14px;
    border-radius: 10px;
}}

QComboBox#DashboardControlCombo {{
    selection-background-color: {accent_dark};
    selection-color: #ffffff;
}}

QComboBox#DashboardControlCombo:hover,
QComboBox#DashboardControlCombo:focus {{
    border: 1px solid {accent_hover};
}}

QComboBox#DashboardControlCombo QAbstractItemView {{
    selection-background-color: {accent_dark};
    selection-color: #ffffff;
}}

QComboBox#DashboardControlCombo QAbstractItemView::item:hover,
QComboBox#DashboardControlCombo QAbstractItemView::item:selected {{
    background-color: {accent_dark};
    color: #ffffff;
}}

QToolButton#DashboardIconToggle:hover {{
    background-color: {accent_dark};
    border: 1px solid {accent_hover};
}}

QToolButton#DashboardIconToggle:checked {{
    background-color: {accent};
    border: 1px solid {accent_hover};
}}

"""
    dark = f"""
/* Dark theme accent consistency pass */
QPushButton:hover,
QPushButton#SidebarButton:hover,
QWidget#SidebarButton:hover,
QPushButton#ToolbarButton:hover,
QPushButton#SmallButton:hover,
QPushButton#ImageRotateButton:hover,
QPushButton#IconButton:hover {{
    background-color: {accent_dark};
    border: 1px solid {accent_hover};
    color: #ffffff;
}}

QFrame#PreviewCard:hover,
QFrame#DetailsCard:hover,
QFrame#ContentPanel:hover,
QFrame#DashboardCard:hover,
QFrame#DashboardItemCard:hover,
QFrame#AssignmentInfoCard:hover,
QFrame#TodoCard:hover,
QFrame#TodoCardDone:hover,
QFrame#TodoEmptyState:hover,
QFrame#MetricCard:hover,
QFrame#HistoryPanel:hover,
QFrame#BrowserItemCard:hover {{
    border: 1px solid {accent_hover};
}}

QFrame#DeadlineSummaryPanel QFrame#AssignmentInfoCard:hover {{
    background-color: #132033;
    border: 1px solid {accent_hover};
}}

QToolButton#SummaryMetricEditButton:hover {{
    background-color: {accent_dark};
    border: 1px solid {accent_hover};
}}

QTreeWidget::item:hover,
QListWidget::item:hover {{
    background-color: {accent_dark};
    color: #ffffff;
}}

QTreeWidget::item:selected,
QListWidget::item:selected {{
    background-color: {accent_dark};
    color: #ffffff;
}}

QMenu::item:selected {{
    background-color: {accent_dark};
    color: #ffffff;
}}
"""

    transparent_label_fix = """
/* Keep card text visually integrated with the card surface.
   This prevents QLabel backgrounds from rendering as black boxes on some Qt/platform combinations. */
QFrame#DashboardItemCard QLabel#CardTitle,
QFrame#DashboardItemCard QLabel#CardMeta,
QFrame#DashboardItemCard QLabel#CardBody,
QFrame#DashboardItemCard QLabel#CardHint,
QFrame#ContentPanel QWidget#SectionHeader,
QFrame#ContentPanel QWidget#SectionHeader QLabel,
QFrame#ContentPanel QLabel#SectionTitle,
QFrame#ContentPanel QLabel#SectionSubtext,
QFrame#AssignmentInfoCard QLabel,
QFrame#TodoCard QLabel#TodoTitle,
QFrame#TodoCard QLabel#TodoTitleDone,
QFrame#TodoCard QLabel#CardMeta,
QFrame#TodoCardDone QLabel#TodoTitle,
QFrame#TodoCardDone QLabel#TodoTitleDone,
QFrame#TodoCardDone QLabel#CardMeta,
QFrame#TodoEmptyState QLabel#TodoEmptyTitle,
QFrame#TodoEmptyState QLabel#TodoEmptyBody,
QWidget#DialogField,
QSlider#DialogSlider {
    background-color: transparent;
    border: none;
}
"""

    if str(theme).lower() != "light":
        return (
            APP_STYLESHEET
            + dynamic
            + dark
            + transparent_label_fix
            + build_component_override_styles(theme, accent)
            + build_zoom_stylesheet(zoom_percent)
            + build_tree_browser_styles(theme, accent, zoom_percent)
            + build_final_slider_styles(theme, accent)
            + build_typography_normalization_styles(zoom_percent, font_style)
            + build_sidebar_nav_styles(theme, accent, zoom_percent)
            + build_export_vault_dialog_styles(theme, accent, zoom_percent)
        )

    light = f"""
/* Complete light theme override */
QWidget {{
    background-color: #f6f8fc;
    color: #172033;
}}

QWidget#Sidebar {{
    background-color: #ffffff;
    border-right: 1px solid #dbe3ef;
}}

QWidget#MiddlePanel {{
    background-color: #f4f7fb;
    border-right: 1px solid #dbe3ef;
}}

QWidget#RightPanel {{
    background-color: #f6f8fc;
}}

QLabel {{
    color: #172033;
    background: transparent;
}}

QLabel#SidebarTitle,
QLabel#PageTitle,
QLabel#LibraryTitle,
QLabel#SectionTitle,
QLabel#CardTitle,
QLabel#BrowserItemTitle,
QLabel#TodoTitle,
QLabel#TodoEmptyTitle,
QLabel#AssignmentInfoValue,
QLabel#MetricValue {{
    color: #0f172a;
}}

QLabel#PageSubtitle,
QLabel#LibrarySubtitle,
QLabel#MutedText,
QLabel#MetaText,
QLabel#DetailKey,
QLabel#BrowserItemMeta,
QLabel#SectionSubtext,
QLabel#CardMeta,
QLabel#CardHint,
QLabel#MetricTitle,
QLabel#SectionCaption,
QLabel#TodoSummary,
QLabel#TodoEmptyBody {{
    color: #64748b;
}}

QLabel#CardBody,
QLabel#DetailValue,
QLabel#BrowserItemSubtitle {{
    color: #334155;
}}

QFrame#PreviewCard,
QFrame#DetailsCard,
QFrame#ContentPanel,
QFrame#DashboardCard,
QFrame#DashboardItemCard,
QFrame#AssignmentInfoCard,
QFrame#TodoCard,
QFrame#TodoCardDone,
QFrame#TodoEmptyState,
QFrame#MetricCard,
QFrame#HistoryPanel,
QFrame#SectionActionBar {{
    background-color: #ffffff;
    border: 1px solid #d7deea;
    border-radius: 18px;
}}

QFrame#PreviewCard:hover,
QFrame#DetailsCard:hover,
QFrame#ContentPanel:hover,
QFrame#DashboardCard:hover,
QFrame#DashboardItemCard:hover,
QFrame#AssignmentInfoCard:hover,
QFrame#TodoCard:hover,
QFrame#TodoCardDone:hover,
QFrame#TodoEmptyState:hover,
QFrame#MetricCard:hover,
QFrame#HistoryPanel:hover {{
    background-color: #f8fbff;
    border: 1px solid {accent};
}}

QFrame#DeadlineSummaryPanel QFrame#AssignmentInfoCard:hover {{
    background-color: #f8fbff;
    border: 1px solid {accent};
}}

QToolButton#SummaryMetricEditButton:hover {{
    background-color: #f8fbff;
    border: 1px solid {accent};
}}

QLabel#TodoEmptyIcon {{
    background-color: #f1f5f9;
    border: 1px solid #d7deea;
}}

QProgressBar#TodoProgressBar {{
    background-color: #e8eef7;
    border: 1px solid #d7deea;
    border-radius: 4px;
}}

QProgressBar#TodoProgressBar::chunk {{
    background-color: #16a34a;
    border-radius: 4px;
}}

QLabel#ScopeContextBar,
QLabel#SidebarUserChip {{
    background-color: #ffffff;
    color: #475569;
    border: 1px solid #d7deea;
}}

QPushButton,
QPushButton#SmallButton,
QPushButton#ImageRotateButton,
QPushButton#IconButton,
QPushButton#DangerIconButton,
QPushButton#FileHeaderIconButton,
QPushButton#SidebarLogoButton,
QPushButton#ToolbarButton {{
    background-color: #ffffff;
    border: 1px solid #d1d9e6;
    color: #172033;
}}

QPushButton#FileHeaderIconButton {{
    background-color: transparent;
    border: 1px solid transparent;
}}

QPushButton#DangerIconButton {{
    background-color: #fff1f2;
    border: 1px solid #fecdd3;
    color: #be123c;
}}

QPushButton#DangerIconButton:hover {{
    background-color: #ffe4e6;
    border: 1px solid #fb7185;
    color: #9f1239;
}}

QWidget#SidebarButton {{
    background-color: transparent;
    border: 1px solid transparent;
}}

QLabel#SidebarButtonIcon {{
    background-color: #f1f5f9;
    border: 1px solid #d1d9e6;
}}

QLabel#SidebarButtonText {{
    color: #172033;
}}

QPushButton:hover,
QPushButton#SmallButton:hover,
QPushButton#ImageRotateButton:hover,
QPushButton#IconButton:hover,
QPushButton#FileHeaderIconButton:hover,
QPushButton#SidebarLogoButton:hover,
QPushButton#ToolbarButton:hover,
QWidget#SidebarButton:hover {{
    background-color: #eef4ff;
    border: 1px solid {accent};
}}

QWidget#SidebarButton:hover QLabel#SidebarButtonIcon {{
    background-color: #ffffff;
    border: 1px solid {accent};
}}

QWidget#SidebarButton:hover QLabel#SidebarButtonText {{
    color: #0f172a;
}}

QPushButton:disabled,
QPushButton#ToolbarButton:disabled {{
    background-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: #94a3b8;
}}

QPushButton[active="true"],
QPushButton#SidebarButton[active="true"],
QWidget#SidebarButton[active="true"] {{
    background-color: {accent};
    border: 1px solid {accent_dark};
    color: #ffffff;
}}

QWidget#SidebarButton[active="true"] QLabel#SidebarButtonIcon {{
    background-color: rgba(255, 255, 255, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.28);
}}

QWidget#SidebarButton[active="true"] QLabel#SidebarButtonText {{
    color: #ffffff;
}}

QListWidget,
QTreeWidget,
QTextEdit,
QPlainTextEdit,
QLineEdit,
QTableWidget {{
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #d7deea;
}}

QTextEdit#PreviewText {{
    background-color: transparent;
    border: none;
    color: #334155;
}}

QTextEdit#CodePreview,
QPlainTextEdit#CodePreview {{
    background-color: #f8fafc;
    color: #0f172a;
    border: 1px solid #d7deea;
}}

QTreeWidget {{
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
}}

QTreeWidget::item {{
    color: #334155;
}}

QTreeWidget::item:hover,
QListWidget::item:hover {{
    background-color: #eef4ff;
    color: #0f172a;
}}

QTreeWidget::item:selected,
QListWidget::item:selected {{
    background-color: #dbeafe;
    color: #0f172a;
}}

QHeaderView::section {{
    background-color: #eef2f7;
    color: #172033;
}}

QFrame#BrowserItemCard {{
    background-color: #ffffff;
    border: 1px solid #d7deea;
}}

QFrame#BrowserItemCard:hover {{
    background-color: #eef4ff;
    border: 1px solid {accent};
}}

QFrame#BrowserItemCard[selected="true"],
QFrame#BrowserItemCard[activeContext="true"] {{
    background-color: #dbeafe;
    border: 1px solid {accent};
}}

QLabel#BrowserItemIcon {{
    background-color: #f1f5f9;
    border: 1px solid #d7deea;
}}

QLabel#StatusBadge {{
    background-color: {accent};
    color: #ffffff;
    border: 1px solid {accent_dark};
}}

QLabel#StatusPill {{
    color: #1e3a8a;
    background-color: #dbeafe;
    border: 1px solid {accent};
}}

QLabel#DuePill {{
    color: #166534;
    background-color: #dcfce7;
    border: 1px solid #22c55e;
}}

QLabel#DuePillSafe {{
    color: #166534;
    background-color: #dcfce7;
    border: 1px solid #22c55e;
}}

QLabel#DuePillSoon {{
    color: #92400e;
    background-color: #fef3c7;
    border: 1px solid #f59e0b;
}}

QLabel#DuePillUrgent {{
    color: #991b1b;
    background-color: #fee2e2;
    border: 1px solid #ef4444;
}}

QLabel#DuePillCompleted,
QLabel#DuePillNone {{
    color: #475569;
    background-color: #e2e8f0;
    border: 1px solid #cbd5e1;
}}

QMenu {{
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #d1d9e6;
    border-radius: 16px;
}}

QMenu::item {{
    color: #172033;
}}

QMenu::item:selected {{
    background-color: {accent};
    color: #ffffff;
}}

QMenu::separator {{
    background: #e2e8f0;
}}

QMenu::item:disabled {{
    color: #7c8aa0;
}}

QToolTip {{
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #d1d9e6;
}}

QScrollBar::handle:vertical {{
    background: #cbd5e1;
}}

QScrollBar::handle:vertical:hover {{
    background: #94a3b8;
}}

QSplitter#ContentSplitter {{
    background-color: #f6f8fc;
}}

QSplitter#ContentSplitter::handle {{
    background-color: transparent;
    border: none;
    margin: 0px;
}}

QSplitter#ContentSplitter::handle:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent,
        stop:0.44 transparent,
        stop:0.45 {accent},
        stop:0.55 {accent},
        stop:0.56 transparent,
        stop:1 transparent
    );
    border: none;
}}

QProgressDialog#CanvasSyncProgress {{
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #d1d9e6;
}}

QProgressDialog#CanvasSyncProgress QLabel {{
    color: #172033;
}}

QProgressDialog#CanvasSyncProgress QProgressBar {{
    background-color: #eef2f7;
    border: 1px solid #d1d9e6;
    color: #172033;
}}

QProgressDialog#CanvasSyncProgress QProgressBar::chunk {{
    background-color: {accent};
}}

QDialog,
QMessageBox,
QInputDialog,
QFileDialog {{
    background-color: #ffffff;
    color: #172033;
}}

QDialog QLabel,
QMessageBox QLabel,
QInputDialog QLabel,
QFileDialog QLabel {{
    color: #172033;
}}

QDialog QPushButton,
QMessageBox QPushButton,
QInputDialog QPushButton,
QFileDialog QPushButton {{
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #d1d9e6;
}}

QDialog QPushButton:hover,
QMessageBox QPushButton:hover,
QInputDialog QPushButton:hover,
QFileDialog QPushButton:hover {{
    background-color: #eef4ff;
    border: 1px solid {accent};
}}

QDialog#ThemedFormDialog,
QDialog#ThemedMessageDialog,
QDialog#ThemedProgressDialog {{
    background-color: #f6f8fc;
}}

QFrame#DialogCard {{
    background-color: #ffffff;
    border: 1px solid #d7deea;
}}

QLabel#DialogTitle {{
    color: #0f172a;
}}

QLabel#DialogSubtitle,
QLabel#FieldHint,
QLabel#DialogDetail {{
    color: #64748b;
}}

QLabel#FieldLabel,
QLabel#DialogBody,
QLabel#DialogStatus,
QLabel#SliderValue {{
    color: #172033;
}}

QLabel#DialogStatus {{
    background-color: #f8fafc;
    border: 1px solid #d7deea;
}}

QLineEdit#DialogInput,
QTextEdit#DialogTextArea,
QComboBox#DialogCombo {{
    background-color: #ffffff;
    border: 1px solid #d1d9e6;
    color: #172033;
    selection-background-color: {accent};
}}

QLineEdit#DialogInput:focus,
QTextEdit#DialogTextArea:focus,
QComboBox#DialogCombo:focus {{
    border: 1px solid {accent};
}}

QPushButton#PrimaryButton {{
    background-color: {accent};
    border: 1px solid {accent_dark};
    color: #ffffff;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {accent_hover};
    border: 1px solid {accent_dark};
    color: #ffffff;
}}

QPushButton#SecondaryButton {{
    background-color: #ffffff;
    border: 1px solid #d1d9e6;
    color: #172033;
}}

QPushButton#SecondaryButton:hover {{
    background-color: #eef4ff;
    border: 1px solid {accent};
    color: #0f172a;
}}

QProgressBar#DialogProgress {{
    background-color: #eef2f7;
    border: 1px solid #d1d9e6;
    color: #172033;
}}

QProgressBar#DialogProgress::chunk {{
    background-color: {accent};
}}

QWidget#DialogField {{
    background-color: transparent;
    border: none;
}}

QSlider#DialogSlider {{
    background-color: transparent;
    border: none;
}}

QSlider#DialogSlider::groove:horizontal {{
    background-color: transparent;
    border: none;
}}

QSlider#DialogSlider::add-page:horizontal {{
    background-color: #dbe3ef;
    border-radius: 4px;
}}

QSlider#DialogSlider::handle:horizontal {{
    background-color: {accent};
    border: 2px solid #ffffff;
}}

QSlider#DialogSlider::handle:horizontal:hover {{
    background-color: {accent_hover};
    border: 2px solid #ffffff;
}}

QSlider#DialogSlider::sub-page:horizontal {{
    background-color: {accent};
    border-radius: 4px;
}}

QCheckBox {{
    color: #172033;
    spacing: 10px;
}}

QCheckBox::indicator {{
    background-color: #ffffff;
    border: 1px solid #94a3b8;
    border-radius: 6px;
}}

QCheckBox::indicator:hover {{
    border: 1px solid {accent_hover};
    background-color: #eef4ff;
}}

QCheckBox::indicator:checked {{
    background-color: {accent};
    border: 1px solid {accent_dark};
    image: url("{check_icon}");
}}

QTreeWidget#ResourceTree,
QTreeWidget#LibraryTree {{
    background-color: #ffffff;
    border: 1px solid #d7deea;
}}

QTreeWidget#ResourceTree::item,
QTreeWidget#LibraryTree::item {{
    color: #223149;
}}

QTreeWidget#ResourceTree::item:hover,
QTreeWidget#LibraryTree::item:hover {{
    background-color: #eef4ff;
    color: #0f172a;
}}

QTreeWidget#ResourceTree::item:selected,
QTreeWidget#ResourceTree::item:selected:active,
QTreeWidget#ResourceTree::item:selected:!active,
QTreeWidget#LibraryTree::item:selected,
QTreeWidget#LibraryTree::item:selected:active,
QTreeWidget#LibraryTree::item:selected:!active {{
    background-color: #dbeafe;
    color: #0f172a;
}}

QFrame#AssignmentListRow {{
    background-color: #ffffff;
    border: 1px solid #d7deea;
}}

QFrame#DashboardProgressPanel {{
    background-color: #ffffff;
    border: 1px solid #d7deea;
}}

QLabel#DashboardProgressValue {{
    color: #0f172a;
}}

QProgressBar#DashboardProgressBar {{
    background-color: #eef2f7;
    border: 1px solid #d1d9e6;
}}

QFrame#AssignmentListRow:hover {{
    background-color: #f8fbff;
    border: 1px solid {accent};
}}

QFrame#AssignmentListRow QLabel#CardTitle {{
    color: #0f172a;
}}

QFrame#AssignmentListRow QLabel#CardMeta {{
    color: #64748b;
}}

QPushButton#AssignmentRowButton {{
    background-color: #ffffff;
    border: 1px solid #d1d9e6;
    color: #172033;
}}

QPushButton#AssignmentRowButton:hover {{
    background-color: #eef4ff;
    border: 1px solid {accent};
    color: #0f172a;
}}

QFrame#ContextQuickBar {{
    background-color: #f8fafc;
    border: 1px solid #d7deea;
}}

QToolButton#ContextQuickButton {{
    background-color: transparent;
    border: none;
}}

QToolButton#ContextQuickButton:hover {{
    background-color: #e8f0ff;
}}

QTextEdit#RichDocumentPreview,
QTextEdit#LibraryDetails {{
    background-color: #ffffff;
    color: #172033;
    border: 1px solid #d7deea;
}}
"""
    return (
        APP_STYLESHEET
        + dynamic
        + light
        + transparent_label_fix
        + build_component_override_styles(theme, accent)
        + build_zoom_stylesheet(zoom_percent)
        + build_tree_browser_styles(theme, accent, zoom_percent)
        + build_final_slider_styles(theme, accent)
        + build_typography_normalization_styles(zoom_percent, font_style)
        + build_sidebar_nav_styles(theme, accent, zoom_percent)
        + build_export_vault_dialog_styles(theme, accent, zoom_percent)
    )


def build_export_vault_dialog_styles(theme="dark", accent="#2563eb", zoom_percent=100):
    """Keep export selection controls prominent without changing global checkboxes."""
    zoom = max(0.7, min(1.8, float(zoom_percent or 100) / 100.0))
    accent = accent or "#2563eb"
    accent_hover = _adjust_hex(accent, 1.22)
    accent_dark = _adjust_hex(accent, 0.72)
    check_icon = _qss_url(_asset_path("icons", "check.svg"))

    def px(value):
        return max(1, int(round(value * zoom)))

    if str(theme).lower() == "light":
        tree_bg = "#ffffff"
        tree_border = "#c9d4e4"
        row_hover = "#edf4ff"
        row_selected = "#dbeafe"
        text = "#172033"
        muted = "#475569"
        strip_bg = "#f8fafc"
        strip_border = "#c9d4e4"
        indicator_bg = "#ffffff"
        indicator_border = "#64748b"
        indicator_hover = "#e8f0ff"
        branch = "#94a3b8"
    else:
        tree_bg = "#0b1220"
        tree_border = "#3b465d"
        row_hover = "#172033"
        row_selected = "#1e2a44"
        text = "#f8fafc"
        muted = "#b8c5d8"
        strip_bg = "#101827"
        strip_border = "#334155"
        indicator_bg = "#111827"
        indicator_border = "#94a3b8"
        indicator_hover = "#172033"
        branch = "#64748b"

    return f"""
/* Export Vault Archive clarity pass */
QLabel#ExportInstruction {{
    color: {muted};
    font-size: {px(13)}px;
    font-weight: 600;
    background: transparent;
}}

QFrame#ExportSummaryStrip {{
    background-color: {strip_bg};
    border: 1px solid {strip_border};
    border-radius: {px(12)}px;
}}

QLabel#ExportSummary {{
    color: {text};
    font-size: {px(13)}px;
    font-weight: 800;
    background: transparent;
}}

QTreeWidget#ExportVaultTree {{
    background-color: {tree_bg};
    border: 1px solid {tree_border};
    border-radius: {px(12)}px;
    padding: {px(8)}px {px(10)}px;
    color: {text};
    outline: none;
}}

QTreeWidget#ExportVaultTree:focus {{
    border: 1px solid {accent_hover};
}}

QTreeWidget#ExportVaultTree::item {{
    min-height: {px(42)}px;
    padding: {px(8)}px {px(10)}px;
    border-radius: {px(8)}px;
    color: {text};
    background: transparent;
}}

QTreeWidget#ExportVaultTree::item:hover {{
    background-color: {row_hover};
    color: {text};
}}

QTreeWidget#ExportVaultTree::item:selected,
QTreeWidget#ExportVaultTree::item:selected:active,
QTreeWidget#ExportVaultTree::item:selected:!active {{
    background-color: {row_selected};
    color: {text};
}}

QTreeWidget#ExportVaultTree::branch,
QTreeWidget#ExportVaultTree::branch:hover,
QTreeWidget#ExportVaultTree::branch:selected {{
    background: transparent;
    color: {branch};
}}

QTreeWidget#ExportVaultTree::indicator {{
    width: {px(23)}px;
    height: {px(23)}px;
    border-radius: {px(7)}px;
    border: 2px solid {indicator_border};
    background-color: {indicator_bg};
    margin-left: {px(2)}px;
    margin-right: {px(10)}px;
}}

QTreeWidget#ExportVaultTree::indicator:hover {{
    border: 2px solid {accent_hover};
    background-color: {indicator_hover};
}}

QTreeWidget#ExportVaultTree::indicator:checked {{
    background-color: {accent};
    border: 2px solid {accent_hover};
    image: url("{check_icon}");
}}

QTreeWidget#ExportVaultTree::indicator:indeterminate {{
    background-color: {accent_dark};
    border: 2px solid {accent_hover};
}}

QTreeWidget#ExportVaultTree::indicator:disabled {{
    background-color: {strip_bg};
    border: 2px solid {strip_border};
}}
"""


def build_sidebar_nav_styles(theme="dark", accent="#2563eb", zoom_percent=100):
    """Final sidebar navigation pass with app-native button styling."""
    zoom = max(0.7, min(1.6, float(zoom_percent or 100) / 100.0))

    def px(value):
        return max(1, int(round(value * zoom)))

    is_light = str(theme).lower() == "light"
    if is_light:
        base_bg = "#ffffff"
        hover_bg = "#eef4ff"
        active_bg = "#eaf1fb"
        pressed_bg = _adjust_hex(accent, 1.68)
        border = "#d7deea"
        active_border = "#b8c4d6"
        hover_border = accent
        icon_bg = "#f1f5f9"
        icon_active_bg = "#ffffff"
        icon_hover_bg = "#ffffff"
        text = "#172033"
        text_hover = "#0f172a"
        active_text = "#0f172a"
        profile_bg = "#eef4ff"
        profile_border = "#b8c4d6"
        profile_icon_bg = "#ffffff"
        profile_school = "#4b5f7a"
        profile_badge_bg = accent
        profile_badge_text = "#ffffff"
        splitter_bg = "#f6f8fc"
        splitter_handle = "#dbe3ef"
        splitter_border = "#cbd5e1"
    else:
        base_bg = "#141b2a"
        hover_bg = "#1f2937"
        active_bg = "#1b2535"
        pressed_bg = _adjust_hex(accent, 0.72)
        border = "#263244"
        active_border = "#3a465a"
        hover_border = accent
        icon_bg = "#101827"
        icon_active_bg = "#202b3c"
        icon_hover_bg = "#172033"
        text = "#dbe7f7"
        text_hover = "#ffffff"
        active_text = "#ffffff"
        profile_bg = "#1b2535"
        profile_border = "#3a465a"
        profile_icon_bg = "#202b3c"
        profile_school = "#9fb1c8"
        profile_badge_bg = accent
        profile_badge_text = "#ffffff"
        splitter_bg = "#0f1117"
        splitter_handle = "#172033"
        splitter_border = "#263244"

    return f"""
/* Final sidebar nav: roomy app-native buttons with hover, press, and active states. */
QWidget#SidebarButton {{
    background-color: {base_bg};
    border: 1px solid {border};
    border-radius: {px(12)}px;
    min-height: {px(54)}px;
}}

QWidget#SidebarButton:hover {{
    background-color: {hover_bg};
    border: 1px solid {hover_border};
}}

QWidget#SidebarButton[pressed="true"] {{
    background-color: {pressed_bg};
    border: 1px solid {hover_border};
}}

QWidget#SidebarButton[active="true"] {{
    background-color: {active_bg};
    border: 1px solid {active_border};
}}

QWidget#SidebarButton[active="true"]:hover {{
    background-color: {hover_bg};
    border: 1px solid {hover_border};
}}

QWidget#SidebarButton[active="true"][pressed="true"] {{
    background-color: {pressed_bg};
    border: 1px solid {hover_border};
}}

QWidget#SidebarButton[collapsed="true"] {{
    border-radius: {px(14)}px;
}}

QLabel#SidebarButtonIcon {{
    background-color: {icon_bg};
    border: none;
    border-radius: {px(10)}px;
    padding: 0px;
    min-width: {px(36)}px;
    max-width: {px(36)}px;
    min-height: {px(36)}px;
    max-height: {px(36)}px;
}}

QWidget#SidebarButton[active="false"] QLabel#SidebarButtonIcon,
QWidget#SidebarButton[pressed="false"] QLabel#SidebarButtonIcon {{
    background-color: {icon_bg};
    border: none;
}}

QWidget#SidebarButton[collapsed="true"] QLabel#SidebarButtonIcon {{
    border-radius: {px(12)}px;
}}

QWidget#SidebarButton:hover QLabel#SidebarButtonIcon {{
    background-color: {icon_hover_bg};
    border: none;
}}

QWidget#SidebarButton[pressed="true"] QLabel#SidebarButtonIcon {{
    background-color: {icon_hover_bg};
    border: none;
}}

QWidget#SidebarButton[active="true"] QLabel#SidebarButtonIcon {{
    background-color: {icon_active_bg};
    border: none;
}}

QWidget#SidebarButton[active="true"]:hover QLabel#SidebarButtonIcon,
QWidget#SidebarButton[active="true"][pressed="true"] QLabel#SidebarButtonIcon {{
    background-color: {icon_hover_bg};
    border: none;
}}

QLabel#SidebarButtonText {{
    color: {text};
    font-size: {px(18)}px;
    font-weight: 700;
    background-color: transparent;
    border: none;
}}

QWidget#SidebarButton:hover QLabel#SidebarButtonText {{
    color: {text_hover};
}}

QWidget#SidebarButton[active="true"] QLabel#SidebarButtonText {{
    color: {active_text};
}}

QWidget#SidebarButton[active="true"]:hover QLabel#SidebarButtonText,
QWidget#SidebarButton[pressed="true"] QLabel#SidebarButtonText {{
    color: #ffffff;
}}

QPushButton#SidebarIconButton {{
    background-color: {base_bg};
    border: 1px solid {border};
    border-radius: {px(12)}px;
    padding: 0px;
    text-align: center;
}}

QPushButton#SidebarIconButton:hover {{
    background-color: {hover_bg};
    border: 1px solid {hover_border};
}}

QPushButton#SidebarIconButton:pressed {{
    background-color: {pressed_bg};
    border: 1px solid {hover_border};
}}

QWidget#SidebarButton[variant="profile"] {{
    background-color: {profile_bg};
    border: 1px solid {profile_border};
    border-radius: {px(16)}px;
    min-height: {px(118)}px;
}}

QWidget#SidebarButton[variant="profile"]:hover {{
    background-color: {hover_bg};
    border: 1px solid {hover_border};
}}

QWidget#SidebarButton[variant="profile"] QLabel#SidebarButtonIcon {{
    background-color: {profile_icon_bg};
    border: none;
    border-radius: {px(14)}px;
    min-width: {px(58)}px;
    max-width: {px(58)}px;
    min-height: {px(58)}px;
    max-height: {px(58)}px;
}}

QWidget#SidebarButton[variant="profile"] QLabel#SidebarButtonText {{
    color: {text_hover};
    font-size: {px(19)}px;
    font-weight: 800;
}}

QWidget#SidebarProfileTextStack {{
    background-color: transparent;
    border: none;
}}

QLabel#SidebarProfileSchool {{
    color: {profile_school};
    font-size: {px(15)}px;
    font-weight: 550;
    background-color: transparent;
    border: none;
}}

QLabel#SidebarProfileBadge {{
    color: {profile_badge_text};
    background-color: {profile_badge_bg};
    border: none;
    border-radius: {px(10)}px;
    padding: {px(5)}px {px(10)}px;
    font-size: {px(12)}px;
    font-weight: 850;
    min-width: {px(58)}px;
}}

QWidget#SidebarButton[variant="profile"][active="true"] {{
    background-color: {profile_bg};
    border: 1px solid {profile_border};
}}

QWidget#SidebarButton[variant="profile"][active="true"]:hover,
QWidget#SidebarButton[variant="profile"][pressed="true"] {{
    background-color: {hover_bg};
    border: 1px solid {hover_border};
}}

QWidget#SidebarButton[variant="profile"][collapsed="true"] {{
    border-radius: {px(18)}px;
    min-height: {px(54)}px;
    max-height: {px(54)}px;
}}

QWidget#SidebarButton[variant="profile"][collapsed="true"] QLabel#SidebarButtonIcon {{
    border-radius: {px(12)}px;
    min-width: {px(42)}px;
    max-width: {px(42)}px;
    min-height: {px(42)}px;
    max-height: {px(42)}px;
}}

QPushButton#SidebarLogoButton {{
    background-color: transparent;
    border: none;
    border-radius: {px(12)}px;
    padding: 0px;
    text-align: center;
}}

QPushButton#SidebarLogoButton:hover {{
    background-color: {icon_hover_bg};
    border: none;
}}

QPushButton#SidebarLogoButton:pressed {{
    background-color: {pressed_bg};
    border: none;
}}

QPushButton#SidebarTitleButton {{
    background-color: transparent;
    border: none;
    border-radius: {px(10)}px;
    padding: {px(4)}px {px(8)}px;
    color: {active_text if str(theme).lower() != "light" else text_hover};
    text-align: left;
    font-size: {px(20)}px;
    font-weight: 800;
}}

QPushButton#SidebarTitleButton:hover {{
    background-color: {hover_bg};
    border: none;
}}

QSplitter#MainSplitter,
QSplitter#ContentSplitter {{
    background-color: {splitter_bg};
}}

QSplitter#MainSplitter::handle {{
    background-color: transparent;
    border: none;
    margin: 0px;
}}

QSplitter#MainSplitter::handle:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent,
        stop:0.44 transparent,
        stop:0.45 {accent},
        stop:0.55 {accent},
        stop:0.56 transparent,
        stop:1 transparent
    );
    border: none;
}}

QSplitter#ContentSplitter::handle {{
    background-color: transparent;
    border: none;
    margin: 0px;
}}

QSplitter#ContentSplitter::handle:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent,
        stop:0.44 transparent,
        stop:0.45 {accent},
        stop:0.55 {accent},
        stop:0.56 transparent,
        stop:1 transparent
    );
    border: none;
}}
"""


def build_final_slider_styles(theme="dark", accent="#2563eb"):
    is_light = str(theme).lower() == "light"
    groove = "#dbe3ef" if is_light else "#263244"
    handle_border = "#ffffff" if is_light else "#93c5fd"
    return f"""
/* Final dynamic slider polish: last pass to prevent native black backing. */
QSlider#DialogSlider,
QSlider#MediaSlider,
QSlider#MediaVolume {{
    background-color: transparent;
    border: none;
}}

QSlider#DialogSlider::groove:horizontal,
QSlider#MediaSlider::groove:horizontal,
QSlider#MediaVolume::groove:horizontal {{
    background-color: {groove};
    border: none;
    border-radius: 4px;
    height: 8px;
}}

QSlider#DialogSlider::add-page:horizontal,
QSlider#MediaSlider::add-page:horizontal,
QSlider#MediaVolume::add-page:horizontal {{
    background-color: {groove};
    border-radius: 4px;
}}

QSlider#DialogSlider::sub-page:horizontal,
QSlider#MediaSlider::sub-page:horizontal,
QSlider#MediaVolume::sub-page:horizontal {{
    background-color: {accent};
    border-radius: 4px;
}}

QSlider#DialogSlider::handle:horizontal,
QSlider#MediaSlider::handle:horizontal,
QSlider#MediaVolume::handle:horizontal {{
    background-color: {accent};
    border: 2px solid {handle_border};
    width: 20px;
    height: 20px;
    margin: -7px -10px;
    border-radius: 10px;
}}
"""


def build_tree_browser_styles(theme="dark", accent="#2563eb", zoom_percent=100):
    """Final tree styling pass owned by the full-row delegate."""
    zoom = max(0.7, min(1.6, float(zoom_percent or 100) / 100.0))

    def px(value):
        return max(1, int(round(value * zoom)))

    if str(theme).lower() == "light":
        tree_bg = "#ffffff"
        tree_border = "#d7deea"
        row_text = "#12304f"
        hover_text = "#0f172a"
        rubber_border = accent or "#2563eb"
        rubber_fill = "rgba(37, 99, 235, 22)"
    else:
        tree_bg = "#0f1724"
        tree_border = "#2b3d58"
        row_text = "#d8e8ff"
        hover_text = "#ffffff"
        rubber_border = "#38bdf8"
        rubber_fill = "rgba(56, 189, 248, 22)"

    return f"""
/* Final folder-browser row styling.
   Full-row hover/selection is painted by FullRowSelectionDelegate, so Qt's
   item/branch backgrounds stay transparent to avoid detached selection boxes. */
QTreeWidget#ResourceTree,
QTreeWidget#LibraryTree {{
    background-color: {tree_bg};
    border: 1px solid {tree_border};
    border-radius: {px(12)}px;
    padding: {px(8)}px;
    outline: none;
    show-decoration-selected: 0;
    alternate-background-color: transparent;
    selection-background-color: transparent;
}}

QTreeWidget#ResourceTree::item,
QTreeWidget#LibraryTree::item {{
    min-height: {px(32)}px;
    padding: {px(7)}px {px(10)}px;
    margin: 0px;
    border: none;
    border-radius: 0px;
    background: transparent;
    color: {row_text};
    font-size: {px(14)}px;
    font-weight: 650;
}}

QTreeWidget#ResourceTree::item:hover,
QTreeWidget#ResourceTree::item:selected,
QTreeWidget#ResourceTree::item:selected:active,
QTreeWidget#ResourceTree::item:selected:!active,
QTreeWidget#LibraryTree::item:hover,
QTreeWidget#LibraryTree::item:selected,
QTreeWidget#LibraryTree::item:selected:active,
QTreeWidget#LibraryTree::item:selected:!active {{
    background: transparent;
    border: none;
    color: {hover_text};
}}

QTreeWidget#ResourceTree::item:focus,
QTreeWidget#LibraryTree::item:focus {{
    outline: none;
    border: none;
}}

QTreeWidget#ResourceTree::branch,
QTreeWidget#ResourceTree::branch:hover,
QTreeWidget#ResourceTree::branch:selected,
QTreeWidget#LibraryTree::branch,
QTreeWidget#LibraryTree::branch:hover,
QTreeWidget#LibraryTree::branch:selected {{
    background: transparent;
    border: none;
}}

QRubberBand {{
    border: 1px dashed {rubber_border};
    background-color: {rubber_fill};
}}
"""


APP_STYLESHEET += """
/* Reusable one-page themed form dialogs */
QDialog#ThemedFormDialog,
QDialog#ThemedMessageDialog,
QDialog#ThemedProgressDialog {
    background-color: #0f1117;
}

QFrame#DialogCard {
    background-color: #141b2a;
    border: 1px solid #263244;
    border-radius: 20px;
}

QWidget#DialogField {
    background-color: transparent;
}

QLabel#DialogTitle {
    color: #f8fafc;
    font-size: 24px;
    font-weight: 800;
    background: transparent;
}

QLabel#DialogSubtitle {
    color: #94a3b8;
    font-size: 13px;
    line-height: 1.4;
    background: transparent;
}

QLabel#FieldLabel {
    color: #e8edf7;
    font-size: 13px;
    font-weight: 700;
    background: transparent;
}

QLabel#FieldHint {
    color: #7c8aa0;
    font-size: 12px;
    background: transparent;
}

QLabel#InlineError {
    color: #fca5a5;
    font-size: 13px;
    font-weight: 700;
    background: transparent;
}

QLineEdit#DialogInput,
QTextEdit#DialogTextArea,
QComboBox#DialogCombo,
QTreeWidget#ExportVaultTree {
    background-color: #0f141d;
    border: 1px solid #2a3448;
    border-radius: 12px;
    padding: 10px 12px;
    color: #e8edf7;
    selection-background-color: #2563eb;
}

QLineEdit#DialogInput:focus,
QTextEdit#DialogTextArea:focus,
QComboBox#DialogCombo:focus,
QTreeWidget#ExportVaultTree:focus {
    border: 1px solid #4f84ff;
}

QTreeWidget#ExportVaultTree::item {
    padding: 8px;
    border-radius: 8px;
    background: transparent;
}

QTreeWidget#ExportVaultTree::item:hover {
    background-color: #172033;
}

QTreeWidget#ExportVaultTree::branch {
    background: transparent;
}

QPushButton#PrimaryButton {
    background-color: #2563eb;
    border: 1px solid #3b82f6;
    color: #ffffff;
    border-radius: 11px;
    padding: 9px 16px;
    font-weight: 800;
    min-width: 96px;
    text-align: center;
}

QPushButton#PrimaryButton:hover {
    background-color: #1d4ed8;
    border: 1px solid #60a5fa;
}

QPushButton#SecondaryButton {
    background-color: #172033;
    border: 1px solid #2a3448;
    color: #dbe7f7;
    border-radius: 11px;
    padding: 9px 16px;
    font-weight: 700;
    min-width: 88px;
    text-align: center;
}

QPushButton#SecondaryButton:hover {
    background-color: #24314a;
    border: 1px solid #4f84ff;
}

QLabel#DialogBody,
QLabel#DialogStatus {
    color: #dbe7f7;
    font-size: 13px;
    line-height: 1.45;
    background: transparent;
}

QLabel#DialogStatus {
    background-color: #0f141d;
    border: 1px solid #263244;
    border-radius: 14px;
    padding: 12px 14px;
    font-weight: 700;
}

QLabel#DialogDetail {
    color: #7c8aa0;
    font-size: 12px;
    background: transparent;
}

QProgressBar#DialogProgress {
    background-color: #0f141d;
    border: 1px solid #263244;
    border-radius: 10px;
    min-height: 20px;
    max-height: 20px;
    text-align: center;
    color: #dbeafe;
    font-size: 11px;
    font-weight: 800;
}

QProgressBar#DialogProgress::chunk {
    background-color: #3b82f6;
    border-radius: 9px;
    margin: 1px;
}

QWidget#DialogField {
    background-color: transparent;
    border: none;
}

QSlider#DialogSlider {
    background-color: transparent;
    border: none;
    min-height: 44px;
    padding: 0px 2px;
}

QSlider#DialogSlider::groove:horizontal {
    background-color: transparent;
    border: none;
    height: 8px;
    margin: 0px 11px;
}

QSlider#DialogSlider::add-page:horizontal {
    background-color: #263244;
    border-radius: 4px;
    height: 8px;
}

QSlider#DialogSlider::sub-page:horizontal {
    background-color: #2563eb;
    border-radius: 4px;
    height: 8px;
}

QSlider#DialogSlider::handle:horizontal {
    background-color: #3b82f6;
    border: 2px solid #93c5fd;
    width: 22px;
    height: 22px;
    margin: -8px -11px;
    border-radius: 11px;
}

QSlider#DialogSlider::handle:horizontal:hover {
    background-color: #60a5fa;
    border: 2px solid #bfdbfe;
}

QLabel#SliderValue {
    color: #f8fafc;
    font-size: 13px;
    font-weight: 800;
    background: transparent;
}

/* Final slider polish: prevents platform/native black backing behind handles. */
QSlider#DialogSlider,
QSlider#MediaSlider,
QSlider#MediaVolume {
    background-color: transparent;
    border: none;
}

QSlider#DialogSlider::groove:horizontal,
QSlider#MediaSlider::groove:horizontal,
QSlider#MediaVolume::groove:horizontal {
    background-color: #263244;
    border: none;
    border-radius: 4px;
    height: 8px;
}

QSlider#DialogSlider::add-page:horizontal,
QSlider#MediaSlider::add-page:horizontal,
QSlider#MediaVolume::add-page:horizontal {
    background-color: #263244;
    border-radius: 4px;
}

QSlider#DialogSlider::sub-page:horizontal,
QSlider#MediaSlider::sub-page:horizontal,
QSlider#MediaVolume::sub-page:horizontal {
    background-color: #2563eb;
    border-radius: 4px;
}

QSlider#DialogSlider::handle:horizontal,
QSlider#MediaSlider::handle:horizontal,
QSlider#MediaVolume::handle:horizontal {
    background-color: #3b82f6;
    border: 2px solid #93c5fd;
    width: 20px;
    height: 20px;
    margin: -7px -10px;
    border-radius: 10px;
}


/* Final context-menu polish override: keeps icons/text centered and removes
   platform-default black backing from menus and submenus. */
QMenu,
QMenu#ContextMenu {
    background-color: #101724;
    color: #edf4ff;
    border: 1px solid #2a3548;
    border-radius: 14px;
    padding: 8px;
    margin: 0px;
}

QMenu::item,
QMenu#ContextMenu::item {
    background-color: transparent;
    color: #edf4ff;
    min-height: 22px;
    padding: 8px 28px 8px 34px;
    margin: 2px 3px;
    border-radius: 9px;
}

QMenu::item:selected,
QMenu#ContextMenu::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}

QMenu::item:disabled,
QMenu#ContextMenu::item:disabled {
    color: #6b7a92;
    background-color: transparent;
}

QMenu::icon,
QMenu#ContextMenu::icon {
    padding-left: 8px;
    padding-right: 8px;
}

QMenu::separator,
QMenu#ContextMenu::separator {
    height: 1px;
    background-color: #263244;
    margin: 7px 8px;
}

QMenu::right-arrow,
QMenu#ContextMenu::right-arrow {
    width: 9px;
    height: 9px;
    padding-right: 10px;
}


/* Universal context-menu polish override: applies to every QMenu, including
   nested submenus created outside the file explorer. */
QMenu {
    background-color: #101724;
    color: #edf4ff;
    border: 1px solid #2a3548;
    border-radius: 14px;
    padding: 8px;
    margin: 0px;
}

QMenu::item {
    background-color: transparent;
    color: #edf4ff;
    min-height: 24px;
    padding: 8px 30px 8px 36px;
    margin: 2px 3px;
    border-radius: 9px;
}

QMenu::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}

QMenu::item:disabled {
    color: #6b7a92;
    background-color: transparent;
}

QMenu::separator {
    height: 1px;
    background-color: #263244;
    margin: 7px 8px;
}

QMenu::icon {
    padding-left: 9px;
    padding-right: 9px;
}

QMenu::right-arrow {
    width: 10px;
    height: 10px;
    padding-right: 10px;
}
"""

APP_STYLESHEET += """
/* Global dashboard */
QFrame#DashboardProgressPanel {
    background-color: #141b2a;
    border: 1px solid #263244;
    border-radius: 18px;
}

QLabel#DashboardProgressValue {
    color: #f8fafc;
    font-size: 46px;
    font-weight: 900;
    background-color: transparent;
}

QProgressBar#DashboardProgressBar {
    background-color: #0f172a;
    border: 1px solid #263244;
    border-radius: 6px;
    min-height: 12px;
    max-height: 12px;
}

QProgressBar#DashboardProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 5px;
}

QFrame#DashboardProgressPanel QLabel,
QFrame#DashboardProgressPanel QWidget#SectionHeader,
QFrame#DashboardProgressPanel QWidget#SectionHeader QLabel {
    background-color: transparent;
    border: none;
}
"""

APP_STYLESHEET += """
/* Deadline-first global dashboard */
QFrame#DeadlineDashboardToolbar {
    background-color: transparent;
    border: none;
    border-radius: 0;
    min-height: 48px;
    max-height: 50px;
}

QFrame#DeadlineToolbarGroup {
    background-color: #101827;
    border: 1px solid #253047;
    border-radius: 10px;
    min-height: 46px;
    max-height: 50px;
}

QComboBox#DashboardControlCombo {
    background-color: #0f172a;
    border: 1px solid #2a3650;
    border-radius: 8px;
    color: #e5eefc;
    min-height: 36px;
    max-height: 36px;
    padding: 0 34px 0 14px;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
}

QComboBox#DashboardControlCombo:hover {
    border-color: #3b4b69;
}

QComboBox#DashboardControlCombo:focus {
    border-color: #4f8cff;
}

QComboBox#DashboardControlCombo::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 32px;
    border: none;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background-color: transparent;
}

QComboBox#DashboardControlCombo::down-arrow {
    image: url("{dashboard_chevron_down_icon}");
    width: 12px;
    height: 12px;
}

QComboBox#DashboardControlCombo QAbstractItemView {
    background-color: #0b1220;
    border: 1px solid #2a3650;
    border-radius: 8px;
    color: #f8fafc;
    outline: 0;
    padding: 4px;
    selection-background-color: #13213c;
    selection-color: #ffffff;
}

QComboBox#DashboardControlCombo QAbstractItemView::item {
    min-height: 30px;
    padding: 6px 12px;
    border-radius: 6px;
}

QComboBox#DashboardControlCombo QAbstractItemView::item:hover,
QComboBox#DashboardControlCombo QAbstractItemView::item:selected {
    background-color: #13213c;
}

QToolButton#DashboardIconToggle {
    background-color: #0f172a;
    border: 1px solid #2a3650;
    border-radius: 8px;
    min-width: 38px;
    max-width: 38px;
    min-height: 38px;
    max-height: 38px;
    padding: 0;
    margin: 0;
}

QToolButton#DashboardIconToggle:hover {
    background-color: #18243a;
    border-color: #5b8dff;
}

QToolButton#DashboardIconToggle:checked {
    background-color: #1d4ed8;
    border-color: #6da1ff;
}

QFrame#DeadlineSummaryPanel {
    background-color: transparent;
    border: none;
    min-height: 112px;
    max-height: 112px;
}

QFrame#DeadlineSummaryPanel QFrame#AssignmentInfoCard {
    background-color: #111b2c;
    border: 1px solid #2f4263;
    border-radius: 10px;
    min-height: 102px;
    max-height: 112px;
    padding: 0;
}

QFrame#DeadlineSummaryPanel QFrame#AssignmentInfoCard:hover {
    background-color: #132033;
    border-color: #5b8dff;
}

QFrame#DeadlineSummaryPanel QLabel#CardMeta {
    color: #a9bddc;
    font-size: 13px;
    font-weight: 800;
    min-height: 18px;
    max-height: 22px;
}

QFrame#DeadlineSummaryPanel QLabel#AssignmentInfoValue {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 900;
    min-height: 24px;
    max-height: 30px;
}

QFrame#DeadlineSummaryPanel QLabel#CardBody {
    color: #dbeafe;
    font-size: 14px;
    font-weight: 600;
    min-height: 20px;
    max-height: 26px;
}

QToolButton#SummaryMetricEditButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 0;
}

QToolButton#SummaryMetricEditButton:hover {
    background-color: #18243a;
    border-color: #3b4b69;
}

QFrame#DeadlineHeroCard {
    background-color: #101827;
    border: 1px solid #263654;
    border-radius: 12px;
    min-height: 132px;
    max-height: 152px;
}

QLabel#DeadlineEyebrow,
QLabel#DeadlineGroupTitle {
    color: #8fb4ff;
    font-size: 11px;
    font-weight: 900;
    background-color: transparent;
}

QLabel#DeadlineHeroTitle {
    color: #f8fafc;
    font-size: 21px;
    font-weight: 900;
    background-color: transparent;
}

QLabel#DeadlineHeroStats {
    color: #bfdbfe;
    font-size: 13px;
    font-weight: 700;
    background-color: transparent;
}

QFrame#DeadlineCountdownPanel {
    background-color: transparent;
    border: none;
    border-radius: 0;
    min-height: 150px;
}

QFrame#DeadlineGroupPanel {
    background-color: #101827;
    border: 1px solid #27334a;
    border-radius: 9px;
}

QLabel#DeadlineGroupCount {
    background-color: #0f172a;
    border: 1px solid #2f3d58;
    border-radius: 10px;
    color: #dbeafe;
    min-width: 22px;
    max-width: 22px;
    min-height: 20px;
    max-height: 20px;
    font-size: 11px;
    font-weight: 900;
}

QFrame#DeadlineAssignmentDanger,
QFrame#DeadlineAssignmentWarning,
QFrame#DeadlineAssignmentSafe,
QFrame#DeadlineAssignmentCompleted,
QFrame#DeadlineAssignmentNone,
QFrame#DeadlineAssignmentCard {
    background-color: #101827;
    border: 1px solid #2a3650;
    border-radius: 8px;
    min-height: 86px;
    max-height: 96px;
}

QFrame#DeadlineAssignmentDanger {
    border-color: #ef4444;
}

QFrame#DeadlineAssignmentWarning {
    border-color: #f59e0b;
}

QFrame#DeadlineAssignmentSafe {
    border-color: #2f7d55;
}

QFrame#DeadlineAssignmentCompleted,
QFrame#DeadlineAssignmentNone {
    background-color: #0f1724;
    border-color: #263244;
}

QFrame#DeadlineDueBadge,
QFrame#DeadlineDueBadgeDanger,
QFrame#DeadlineDueBadgeWarning,
QFrame#DeadlineDueBadgeSafe,
QFrame#DeadlineDueBadgeCompleted,
QFrame#DeadlineDueBadgeNone {
    border-radius: 8px;
    border: 1px solid #34435f;
    background-color: #0f172a;
    min-width: 86px;
    max-width: 104px;
    min-height: 42px;
    max-height: 46px;
}

QFrame#DeadlineDueBadgeDanger {
    background-color: #7f1d1d;
    border-color: #ef4444;
}

QFrame#DeadlineDueBadgeWarning {
    background-color: #78350f;
    border-color: #f59e0b;
}

QFrame#DeadlineDueBadgeSafe {
    background-color: #14532d;
    border-color: #22c55e;
}

QFrame#DeadlineDueBadgeCompleted,
QFrame#DeadlineDueBadgeNone {
    background-color: #334155;
    border-color: #64748b;
}

QLabel#DeadlineCardCountdown {
    color: #f8fafc;
    font-size: 20px;
    font-weight: 900;
    background-color: transparent;
}

QFrame#DeadlineDueBadgeWarning QLabel#DeadlineCardCountdown {
    color: #fef3c7;
}

QFrame#DeadlineDueBadgeSafe QLabel#DeadlineCardCountdown {
    color: #dcfce7;
}

QFrame#DeadlineDueBadgeDanger QLabel#DeadlineCardCountdown {
    color: #fee2e2;
}

QFrame#DeadlineDueBadgeCompleted QLabel#DeadlineCardCountdown,
QFrame#DeadlineDueBadgeNone QLabel#DeadlineCardCountdown {
    color: #e2e8f0;
}

QLabel#DeadlineMoreLabel {
    background-color: #0f172a;
    border: 1px dashed #34435f;
    border-radius: 8px;
    color: #9fb4d6;
    min-height: 28px;
    max-height: 28px;
    font-size: 12px;
    font-weight: 800;
}

QFrame#DeadlineTimelineItem {
    background-color: #101827;
    border: 1px solid #263244;
    border-radius: 8px;
    min-width: 150px;
    max-width: 150px;
    min-height: 76px;
    max-height: 76px;
}

QFrame#DeadlineTimelineClusterItem {
    background-color: #102033;
    border: 1px solid #38bdf8;
    border-radius: 8px;
    min-width: 150px;
    max-width: 150px;
    min-height: 76px;
    max-height: 76px;
}

QFrame#DeadlineTimelineClusterItem:hover {
    background-color: #132a43;
    border: 1px solid #7dd3fc;
}

QFrame#DeadlineTimelineClusterItem QLabel#DeadlineTimelineTitle {
    color: #e0f2fe;
}

QFrame#DeadlineTimelineClusterItem QLabel#CardMeta {
    color: #bae6fd;
}

QLabel#DeadlineTimelineClusterBadge {
    background-color: #0e7490;
    border: 1px solid #67e8f9;
    border-radius: 9px;
    color: #ecfeff;
    min-width: 18px;
    max-width: 34px;
    padding: 0 5px;
    font-size: 10px;
    font-weight: 900;
}

QWidget#ScaledTimeline {
    background-color: transparent;
    border: none;
}

QScrollArea#TimelineScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea#TimelineScrollArea > QWidget {
    background-color: transparent;
}

QLabel#DeadlineTimelineDate {
    color: #7dd3fc;
    font-size: 11px;
    font-weight: 900;
    background-color: transparent;
}

QLabel#DeadlineTimelineTitle {
    color: #f8fafc;
    font-size: 13px;
    font-weight: 800;
    background-color: transparent;
}

QPushButton#PrimarySmallButton {
    background-color: #7c3aed;
    border: 1px solid #8b5cf6;
    border-radius: 8px;
    color: #ffffff;
    min-height: 34px;
    padding: 6px 14px;
    font-weight: 800;
}

QPushButton#PrimarySmallButton:hover {
    background-color: #6d28d9;
}
""".replace(
    "{dashboard_chevron_down_icon}",
    _qss_url(_asset_path("icons", "chevron-down.svg")),
)

APP_STYLESHEET += """
/* Final selected-row visibility fix: keep multi-selected tree/list rows visibly
   highlighted even when the mouse is not hovering and when the widget loses focus. */
QTreeWidget::item:selected,
QTreeWidget::item:selected:active,
QTreeWidget::item:selected:!active,
QListWidget::item:selected,
QListWidget::item:selected:active,
QListWidget::item:selected:!active {
    background-color: #1f3b77;
    color: #ffffff;
    border: none;
}

QTreeWidget::item:selected:hover,
QListWidget::item:selected:hover {
    background-color: #25509e;
    color: #ffffff;
}

"""

APP_STYLESHEET += """
/* Windows 11 inspired compact command strip for context menus */
QFrame#ContextQuickBar {
    background-color: transparent;
    border: none;
    border-radius: 10px;
}

QToolButton#ContextQuickButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 7px;
    min-width: 30px;
    min-height: 30px;
    max-width: 34px;
    max-height: 34px;
}

QToolButton#ContextQuickButton:hover {
    background-color: #1f2a3d;
}

QToolButton#ContextQuickButton:pressed {
    background-color: #2563eb;
}

QToolButton#ContextQuickButton:disabled {
    background-color: transparent;
    opacity: 0.45;
}
"""

APP_STYLESHEET += """
/* Text-editor-inspired menu finish: cleaner spacing with the same Win11 command layout. */
QMenu {
    background-color: #0f1724;
    color: #eef6ff;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 6px;
}

QMenu::item {
    background-color: transparent;
    color: #eef6ff;
    min-height: 24px;
    padding: 7px 30px 7px 34px;
    margin: 1px 2px;
    border-radius: 7px;
}

QMenu::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}

QMenu::item:disabled {
    color: #64748b;
    background-color: transparent;
}

QMenu::separator {
    height: 1px;
    background-color: #263244;
    margin: 6px 7px;
}

QMenu::icon {
    padding-left: 8px;
    padding-right: 9px;
}

QMenu::right-arrow {
    width: 10px;
    height: 10px;
    padding-right: 9px;
}

QFrame#ContextQuickBar {
    background-color: rgba(15, 23, 36, 0.98);
    border: none;
    border-radius: 9px;
}

QToolButton#ContextQuickButton {
    background-color: transparent;
    border: none;
    border-radius: 7px;
    padding: 6px;
    min-width: 30px;
    min-height: 30px;
    max-width: 34px;
    max-height: 34px;
}

QToolButton#ContextQuickButton:hover {
    background-color: #1e293b;
}

QToolButton#ContextQuickButton:pressed {
    background-color: #2563eb;
}
"""

APP_STYLESHEET += """
/* Premium context menu finish: larger blue-tinted bold labels, larger icons,
   and clear shortcut spacing while preserving the current Win11-style layout. */
QMenu {
    background-color: #0d1625;
    color: #cfe2ff;
    border: 1px solid #38547a;
    border-radius: 14px;
    padding: 8px;
    icon-size: 22px;
    font-size: 14px;
    font-weight: 700;
}

QMenu::item {
    background-color: transparent;
    color: #cfe2ff;
    min-height: 30px;
    padding: 9px 44px 9px 42px;
    margin: 2px 3px;
    border-radius: 9px;
}

QMenu::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}

QMenu::item:disabled {
    color: #71819a;
    background-color: transparent;
}

QMenu::separator {
    height: 1px;
    background-color: #2b3a52;
    margin: 7px 8px;
}

QMenu::icon {
    padding-left: 10px;
    padding-right: 12px;
}

QMenu::right-arrow {
    width: 11px;
    height: 11px;
    padding-right: 10px;
}

QFrame#ContextQuickBar {
    background-color: rgba(13, 22, 37, 0.98);
    border: 1px solid rgba(56, 84, 122, 0.35);
    border-radius: 11px;
}

QToolButton#ContextQuickButton {
    background-color: transparent;
    border: none;
    border-radius: 9px;
    padding: 7px;
    min-width: 36px;
    min-height: 36px;
    max-width: 40px;
    max-height: 40px;
}

QToolButton#ContextQuickButton:hover {
    background-color: #1f3b77;
}

QToolButton#ContextQuickButton:pressed {
    background-color: #2563eb;
}
"""

APP_STYLESHEET += """

/* Larger, more readable document previews. */
QTextEdit#RichDocumentPreview {
    background-color: #0b1220;
    border: 1px solid #263244;
    border-radius: 16px;
    padding: 16px;
    color: #dbeafe;
    font-family: "Inter", "Segoe UI", "SF Pro Display", sans-serif;
    font-size: 14px;
    selection-background-color: #2563eb;
}

QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QTextEdit#LibraryDetails {
    background-color: #0b1220;
    border: 1px solid #263244;
    border-radius: 16px;
    padding: 16px;
    color: #dbeafe;
    font-family: "Inter", "Segoe UI", "SF Pro Display", sans-serif;
    font-size: 14px;
}
"""

APP_STYLESHEET += """

/* Premium resource tree styling: main file explorer and Resource Library. */
QTreeWidget#ResourceTree,
QTreeWidget#LibraryTree {
    background-color: #0f1724;
    border: 1px solid #2b3d58;
    border-radius: 16px;
    padding: 12px;
    show-decoration-selected: 1;
}

QTreeWidget#ResourceTree::item,
QTreeWidget#LibraryTree::item {
    min-height: 42px;
    padding: 10px 12px;
    color: #d8e8ff;
    font-size: 15px;
    font-weight: 650;
}

QTreeWidget#ResourceTree::item:hover,
QTreeWidget#LibraryTree::item:hover {
    background-color: #1a2940;
    color: #f4f9ff;
}

QTreeWidget#ResourceTree::item:selected,
QTreeWidget#ResourceTree::item:selected:active,
QTreeWidget#ResourceTree::item:selected:!active,
QTreeWidget#LibraryTree::item:selected,
QTreeWidget#LibraryTree::item:selected:active,
QTreeWidget#LibraryTree::item:selected:!active {
    background-color: #25509e;
    color: #ffffff;
    border: none;
}

QTreeWidget#ResourceTree::item:selected:hover,
QTreeWidget#LibraryTree::item:selected:hover {
    background-color: #2f67c8;
}

QTreeWidget#ResourceTree::branch,
QTreeWidget#LibraryTree::branch,
QTreeWidget#ResourceTree::branch:hover,
QTreeWidget#LibraryTree::branch:hover,
QTreeWidget#ResourceTree::branch:selected,
QTreeWidget#LibraryTree::branch:selected {
    background: transparent;
}

QFrame#AssignmentListRow {
    background-color: #101927;
    border: 1px solid #26364e;
    border-radius: 8px;
}

QFrame#AssignmentListRow:hover {
    background-color: #142033;
    border: 1px solid #3d5f93;
}

QFrame#AssignmentListRow QLabel#CardTitle {
    color: #f8fbff;
    font-size: 16px;
    font-weight: 800;
}

QLabel#AssignmentDueDate {
    color: #d8e8ff;
    font-size: 14px;
    font-weight: 750;
}

QFrame#AssignmentListRow QLabel#CardMeta {
    color: #aac0dc;
    font-size: 13px;
    font-weight: 600;
}

QFrame#AssignmentListRow QLabel#DuePill,
QFrame#AssignmentListRow QLabel#DuePillSafe,
QFrame#AssignmentListRow QLabel#DuePillSoon,
QFrame#AssignmentListRow QLabel#DuePillUrgent,
QFrame#AssignmentListRow QLabel#DuePillCompleted,
QFrame#AssignmentListRow QLabel#DuePillNone {
    border-radius: 11px;
    padding: 5px 13px;
    min-width: 90px;
    font-size: 11px;
    font-weight: 800;
}

QPushButton#AssignmentRowButton {
    background-color: #142033;
    border: 1px solid #2b3f5e;
    border-radius: 9px;
    color: #e7f0ff;
    padding: 7px 11px;
    min-width: 0px;
    font-size: 12px;
    font-weight: 650;
    text-align: center;
}

QPushButton#AssignmentRowButton:hover {
    background-color: #1b2b44;
    border: 1px solid #4f84ff;
    color: #ffffff;
}

QPushButton#AssignmentRowButton:pressed {
    background-color: #25509e;
    border: 1px solid #6fa0ff;
}
"""
