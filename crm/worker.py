"""Railway worker entrypoint:  python -m crm.worker   (loop)  |  --once"""
import sys
import time

from . import create_app
from .services.scheduled_actions import poll_once

POLL_SECONDS = 30


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    app = create_app()
    with app.app_context():
        if "--once" in argv:
            print(poll_once())
            return
        while True:
            try:
                stats = poll_once()
                if any(stats.values()):
                    print(stats, flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"poll error: {exc}", flush=True)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
