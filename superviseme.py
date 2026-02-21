import os
import sys

# Ensure the project root is on the path so both 'superviseme' and 'scripts'
# packages are importable regardless of the working directory.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv()

from superviseme import create_app, db
from argparse import ArgumentParser


def _run_seed_if_needed():
    """Seed the database when SKIP_DB_SEED is not 'true'.

    Mirrors the behaviour of docker-entrypoint.sh so that non-Docker
    environments get the same initial data as the Docker development setup.
    """
    if os.getenv("SKIP_DB_SEED", "true").lower() == "true":
        return

    import importlib.util
    seed_path = os.path.join(_ROOT, "scripts", "seed_database.py")
    spec = importlib.util.spec_from_file_location("seed_database", seed_path)
    seed_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_mod)
    print("Running database seeding (SKIP_DB_SEED != true)…")
    seed_mod.seed_database()


def start_app(db_type="sqlite", debug=False, host="localhost", port=8080):
    _run_seed_if_needed()
    app = create_app(db_type=db_type)
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument(
        "-x", "--host", default="localhost", help="host address to run the app on"
    )
    parser.add_argument("-y", "--port", default="8080", help="port to run the app on")
    parser.add_argument(
        "-d", "--debug", default=False, action="store_true", help="debug mode"
    )
    parser.add_argument(
        "-D",
        "--db",
        choices=["sqlite", "postgresql"],
        default="sqlite",
        help="Database type",
    )

    args = parser.parse_args()

    start_app(db_type=args.db, debug=args.debug, host=args.host, port=args.port)
