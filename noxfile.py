from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List

from nox_poetry import Session, session

HERE = Path(__file__).parent


@dataclass
class Libraries:
    trickster: List[Path]

    @property
    def all(self) -> List[Path]:
        return [*self.trickster]

    def get(self, category: str) -> List[Path]:
        return self.__getattribute__(category)


@dataclass
class Tests:
    unit: List[Path]
    integration: List[Path]

    @property
    def all(self) -> List[Path]:
        return [*self.unit, *self.integration]

    def get(self, category: str) -> List[Path]:
        return self.__getattribute__(category)


@dataclass
class Repo:
    libraries: Libraries
    tests: Tests
    dev: List[Path]

    @property
    def all(self) -> List[Path]:
        return [*self.libraries.all, *self.tests.all, *self.dev]

    def get(self, *categories: str) -> List[Path]:
        node = self
        for category in categories:
            node = node.__getattribute__(category)
        return node


REPO = Repo(
    libraries=Libraries(
        [HERE / "trickster"],
    ),
    tests=Tests(
        unit=[HERE / "tests" / "unit"],
        integration=[HERE / "tests" / "integration"],
    ),
    dev=[
        HERE / "app.py",
        HERE / "cli.py",
        HERE / "gunicorn.conf.py",
        HERE / "noxfile.py",
        HERE / "setup.py",
    ],
)


@lru_cache
def get_files(session: Session, *categories: str) -> List[str]:
    args = session.posargs or REPO.get(*categories)
    return [str(arg) for arg in args]


@session(python=["3.8"])
def unit_tests(session: Session) -> None:
    session.install(".", "pytest", "pytest-mock")
    session.run("pytest", *get_files(session, "tests", "unit"))


@session(python=["3.8"])
def integration_tests(session: Session) -> None:
    session.install(".", "pytest", "pytest-mock")
    session.run("pytest", *get_files(session, "tests", "integration"))


@session(python=["3.8"])
def black(session: Session) -> None:
    session.install("black")
    session.run("black", *get_files(session, "all"))


@session(python=["3.8"])
def lint(session: Session) -> None:
    session.install("flake8", "flake8-import-order")
    session.run("flake8", "--import-order-style", "google", *get_files(session, "all"))
