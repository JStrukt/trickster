from pathlib import Path

from nox_poetry import Session, session

HERE = Path(__file__).parent

LOCATIONS = [
    HERE / "tests",
    HERE / "trickster",
    HERE / "app.py",
    HERE / "cli.py",
    HERE / "gunicorn.conf.py",
    HERE / "noxfile.py",
    HERE / "setup.py",
]


@session(python=["3.8"])
def test(session: Session) -> None:
    session.install(".", "pytest", "pytest-mock")
    session.run("pytest")


@session(python=["3.8"])
def black(session: Session) -> None:
    args = session.posargs or LOCATIONS
    args = [str(arg) for arg in args]
    session.install("black")
    session.run("black", *args)


@session(python=["3.8"])
def lint(session: Session) -> None:
    args = session.posargs or LOCATIONS
    args = [str(arg) for arg in args]
    session.install("flake8")
    session.install("flake8-import-order")
    # session.run("flake8", "--import-order-style", "google")
    session.run("flake8", "--import-order-style", "google", *args)
