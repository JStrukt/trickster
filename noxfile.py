from nox_poetry import session, Session


LOCATIONS = [
    "tests",
    "trickster",
    "app.py",
    "cli.py",
    "gunicorn.conf.py",
    "noxfile.py",
    "setup.py",
]


@session(python=["3.8"])
def test(session: Session) -> None:
    session.install(".", "pytest", "pytest-mock")
    session.run("pytest")


@session
def lint(session: Session) -> None:
    args = session.posargs or LOCATIONS
    session.install("flake8")
    # session.run("flake8", "--import-order-style", "google")
    session.run("flake8", *args)


@session
def black(session: Session) -> None:
    args = session.posargs or LOCATIONS
    session.install("black")
    session.run("black", *args)
