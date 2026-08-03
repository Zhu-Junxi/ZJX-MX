import sys

from PySide6.QtWidgets import QApplication, QStyleFactory

from app.app_info import APP_NAME, APP_ORGANIZATION, APP_VERSION
from app.main_window import MainWindow
from app.settings import AppSettings
from app.styles import APP_STYLESHEET
from app.windows_integration import NOTIFICATION_APP_NAME, configure_windows_notification_identity
from services.app_logging import log_info, setup_app_logging
from ui.icons import load_app_icon


def parse_launch_args(argv):
    started_from_startup = "--startup" in argv
    return {
        "started_from_startup": started_from_startup,
    }


def main():
    configure_windows_notification_identity()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if hasattr(app, "setApplicationDisplayName"):
        app.setApplicationDisplayName(NOTIFICATION_APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORGANIZATION)

    settings = AppSettings()
    setup_app_logging(settings.get_vault_path(), APP_NAME, APP_VERSION)

    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(APP_STYLESHEET)

    launch_args = parse_launch_args(sys.argv[1:])
    window = MainWindow(
        started_from_startup=launch_args["started_from_startup"],
    )
    log_info("Launch arguments: %s", launch_args)
    if window.should_show_on_launch():
        window.show()

    exit_code = app.exec()
    log_info("Application exited with code %s", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
