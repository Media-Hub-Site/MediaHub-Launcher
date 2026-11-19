import os
import sys
import threading
import traceback
from PyQt6.QtWidgets import QApplication
from core.ui.hub_window import HubWindow


def _log_unhandled_error(exc_type, exc_value, exc_traceback):
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        sys.stderr.write(err_msg + "\n")
    except Exception:
        pass
    try:
        home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        log_dir = os.path.join(home, ".mediahub")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "launcher_errors.log"), "a", encoding="utf-8") as f:
            f.write(err_msg + "\n" + ("-" * 60) + "\n")
    except Exception:
        pass


def global_exception_handler(exc_type, exc_value, exc_traceback):
    # Nunca invocar QMessageBox desde hilos secundarios (evita bloqueo "Error Fatal (No responde)")
    # y registrar silenciosamente cualquier excepción menor en tiempo de ejecución.
    _log_unhandled_error(exc_type, exc_value, exc_traceback)


def thread_exception_handler(args):
    _log_unhandled_error(args.exc_type, args.exc_value, args.exc_traceback)


sys.excepthook = global_exception_handler
threading.excepthook = thread_exception_handler


def main():
    app = QApplication(sys.argv)
    window = HubWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

