from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QEvent, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QAbstractScrollArea, QScrollArea, QWidget


@dataclass
class _InertiaState:
    """Runtime velocity state for one scrollbar."""

    velocity: float = 0.0
    remainder: float = 0.0
    timer: QTimer | None = None


class ScrollTuner(QObject):
    """Apply app-wide scroll-speed tuning and optional inertia.

    Qt normally sends wheel events to the exact widget under the cursor. In a
    card-heavy UI this may be a QLabel, QPushButton, or a nested QWidget inside
    a QScrollArea, not the scroll area itself. The previous implementation only
    listened to the scroll area and viewport, so many wheel events still used
    Qt's default fast scrolling. This version installs the filter on the scroll
    surface *and* its content subtree, then keeps newly-added children covered.
    """

    MIN_PERCENT = 10
    MAX_PERCENT = 120
    DEFAULT_PERCENT = 45
    BASE_WHEEL_STEP = 56
    TIMER_INTERVAL_MS = 16
    INERTIA_FRICTION = 0.76
    STOP_VELOCITY = 0.20

    def __init__(self, percent_getter=None, inertia_getter=None, parent=None):
        super().__init__(parent)
        self.percent_getter = percent_getter or (lambda: self.DEFAULT_PERCENT)
        self.inertia_getter = inertia_getter or (lambda: True)
        self._targets = {}
        self._registered_scroll_areas = []
        self._states = {}

    def register(self, widget):
        """Register any QAbstractScrollArea: list, tree, text edit, scroll area.

        Item views such as QListWidget/QTreeWidget sometimes consume wheel
        events very early. For those widgets we also install a direct wheel
        handler when the class supports it. This makes the setting reliable in
        the middle browser and Resource Library instead of only working inside
        plain QScrollArea pages.
        """
        if not isinstance(widget, QAbstractScrollArea):
            return

        if widget not in self._registered_scroll_areas:
            self._registered_scroll_areas.append(widget)

        widget.verticalScrollBar().setSingleStep(10)
        widget.horizontalScrollBar().setSingleStep(10)

        # Match item-view scrolling to the right-side QScrollArea panels.
        # Without this, QListWidget/QTreeWidget scroll by whole rows, so the
        # speed slider cannot feel consistent. Pixel mode gives every panel the
        # same tuned wheel behaviour.
        if isinstance(widget, QAbstractItemView):
            widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            widget.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self._bind_direct_wheel_handler(widget)

        self._install_target_tree(widget, widget)
        self._install_target_tree(widget.viewport(), widget)

        if isinstance(widget, QScrollArea) and widget.widget() is not None:
            self._install_target_tree(widget.widget(), widget)

    def refresh(self):
        """Re-scan registered scroll areas after dynamic page/card rebuilds."""
        for widget in list(self._registered_scroll_areas):
            if widget is not None:
                self.register(widget)

    def eventFilter(self, watched, event):
        event_type = event.type()

        if event_type == QEvent.Type.Wheel and watched in self._targets:
            return self._handle_wheel(self._targets[watched], event)

        if event_type == QEvent.Type.ChildAdded and watched in self._targets:
            child = event.child()
            owner = self._targets[watched]
            if child is not None:
                QTimer.singleShot(0, lambda child=child, owner=owner: self._install_target_tree(child, owner))

        return super().eventFilter(watched, event)

    def _install_target_tree(self, obj, owner):
        if obj is None:
            return

        self._install_target(obj, owner)

        find_children = getattr(obj, "findChildren", None)
        if find_children is None:
            return

        # Only recurse through QWidget children. Scanning every QObject can touch
        # internal Qt helper objects and shortcuts, which produced noisy
        # ``addMetaMethod ... No Wrapper found`` warnings in PySide. Wheel
        # events are delivered to widgets, so QObject-level filtering is not
        # needed here.
        for child in find_children(QWidget):
            self._install_target(child, owner)

    def _install_target(self, obj, owner):
        if obj is None:
            return

        existing_owner = self._targets.get(obj)
        if existing_owner is not None:
            if existing_owner is owner:
                return

            existing_is_outer = (
                isinstance(existing_owner, QWidget)
                and isinstance(owner, QWidget)
                and existing_owner.isAncestorOf(owner)
            )
            owner_contains_target = isinstance(owner, QWidget) and owner.isAncestorOf(obj)
            if existing_is_outer and owner_contains_target:
                self._targets[obj] = owner
            return

        self._targets[obj] = owner
        obj.installEventFilter(self)

    def _bind_direct_wheel_handler(self, widget):
        setter = getattr(widget, "set_wheel_handler", None)

        if setter is None:
            return

        setter(lambda event, scroll_widget=widget: self.handle_wheel_event(scroll_widget, event))

    def handle_wheel_event(self, widget, event):
        """Public hook used by custom list/tree widgets.

        Returning True means the event was fully handled by the tuned scrolling
        system and the widget should not call the default Qt wheel handler.
        """
        return self._handle_wheel(widget, event)

    def _current_factor(self):
        try:
            percent = int(self.percent_getter())
        except (TypeError, ValueError):
            percent = self.DEFAULT_PERCENT

        percent = max(self.MIN_PERCENT, min(self.MAX_PERCENT, percent))
        return percent / 100.0

    def _inertia_enabled(self):
        try:
            return bool(self.inertia_getter())
        except Exception:
            return True

    def _handle_wheel(self, widget, event):
        scroll_delta = self._event_to_scroll_delta(widget, event)

        if scroll_delta is None:
            return False

        bar, delta = scroll_delta

        if not bar.isVisible():
            return False

        if self._inertia_enabled():
            self._add_inertia_delta(bar, delta)
        else:
            self._apply_bar_delta(bar, delta)

        event.accept()
        return True

    def _event_to_scroll_delta(self, widget, event):
        factor = self._current_factor()
        pixel_delta = event.pixelDelta()
        angle_delta = event.angleDelta()

        use_horizontal = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        primary_bar = widget.horizontalScrollBar() if use_horizontal else widget.verticalScrollBar()
        fallback_bar = widget.verticalScrollBar() if use_horizontal else widget.horizontalScrollBar()

        if pixel_delta and not pixel_delta.isNull():
            raw_delta = pixel_delta.x() if use_horizontal and pixel_delta.x() else pixel_delta.y()
            if not raw_delta and pixel_delta.x():
                raw_delta = pixel_delta.x()
            scroll_amount = raw_delta * factor
        elif angle_delta and not angle_delta.isNull():
            raw_delta = angle_delta.x() if use_horizontal and angle_delta.x() else angle_delta.y()
            if not raw_delta and angle_delta.x():
                raw_delta = angle_delta.x()
            scroll_amount = (raw_delta / 120.0) * self.BASE_WHEEL_STEP * factor
        else:
            return None

        if not primary_bar.isVisible() and fallback_bar.isVisible():
            primary_bar = fallback_bar

        if not primary_bar.isVisible():
            return None

        # Qt wheel deltas are positive when scrolling up. Scrollbar values move
        # in the opposite direction, so invert here once and use value += delta.
        return primary_bar, -float(scroll_amount)

    def _add_inertia_delta(self, bar, delta):
        state = self._states.get(bar)

        if state is None:
            state = _InertiaState()
            timer = QTimer(self)
            timer.setInterval(self.TIMER_INTERVAL_MS)
            timer.timeout.connect(lambda bar=bar: self._step_inertia(bar))
            state.timer = timer
            self._states[bar] = state

        # Choose the initial velocity so the decaying series totals roughly the
        # requested wheel delta. This keeps the speed setting honest while adding
        # a smooth glide instead of extra runaway distance.
        impulse = delta * (1.0 - self.INERTIA_FRICTION)

        # If the user reverses direction, reset the old momentum so the UI feels
        # controllable instead of fighting against their hand.
        if state.velocity and (state.velocity > 0) != (impulse > 0):
            state.velocity = 0.0
            state.remainder = 0.0

        state.velocity += impulse

        if state.timer is not None and not state.timer.isActive():
            state.timer.start()

    def _step_inertia(self, bar):
        state = self._states.get(bar)

        if state is None:
            return

        if not bar.isVisible() or abs(state.velocity) < self.STOP_VELOCITY:
            if state.timer is not None:
                state.timer.stop()
            state.velocity = 0.0
            state.remainder = 0.0
            return

        self._apply_bar_delta(bar, state.velocity, state)
        state.velocity *= self.INERTIA_FRICTION

    def _apply_bar_delta(self, bar, delta, state=None):
        if state is None:
            amount = int(round(delta))
        else:
            state.remainder += delta
            amount = int(state.remainder)
            state.remainder -= amount

        if amount == 0:
            return

        old_value = bar.value()
        bar.setValue(old_value + amount)

        if bar.value() == old_value and state is not None:
            # We hit a boundary. Stop momentum immediately.
            state.velocity = 0.0
            state.remainder = 0.0
            if state.timer is not None:
                state.timer.stop()
