from nox_poetry import session, Session


@session(python=["3.8"])
def test(session: Session) -> None:
    session.install(".", "pytest", "pytest-mock")
    session.run("pytest")


@session
def lint(session: Session) -> None:
    session.install("flake8")
    # session.run("flake8", "--import-order-style", "google")
    session.run("flake8")
