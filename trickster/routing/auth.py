"""Authentication module."""

from __future__ import annotations

import abc
import datetime
import hashlib
import hmac
import re
from typing import Any, Dict, Iterator, Optional, Tuple, Type
import urllib.parse

import basicauth
from trickster.routing import (
    AuthenticationError,
    Delay,
    Response,
    RouteConfigurationError,
)
from trickster.routing.input import IncomingRequest


class Auth(abc.ABC):
    """Authentication class."""

    method: Optional[str] = None

    def __init__(self, *args: Any, **kwargs: Any):  # pragma: no cover
        # Exists just make to make mypy happy.
        pass

    @abc.abstractmethod
    def authenticate(self, request: IncomingRequest) -> None:
        """Check if IncomingRequest contains valid authentication, raise exception if not."""

    @abc.abstractmethod
    def serialize(self) -> Optional[Dict[str, Any]]:
        """Convert Auth to json value."""

    @classmethod
    def _get_subclasses(cls) -> Iterator[Type[Auth]]:
        """Get all (direct and indirect) subclasses of this class."""
        for subclass in cls.__subclasses__():
            yield from subclass._get_subclasses()
            yield subclass

    @classmethod
    def _find_implementation(cls, method: str) -> Type[Auth]:
        """Find a subclass implementing given auth method."""
        for subclass in cls._get_subclasses():
            if subclass.method == method:
                return subclass
        raise RouteConfigurationError(
            f'Implementation of "{method}"" authentication method not found.'
        )

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> Auth:
        """Convert json value to Auth."""
        if data is None:
            return NoAuth()

        if "method" in data:
            implementation = cls._find_implementation(data["method"])
            if issubclass(implementation, AuthWithResponse):
                return AuthWithResponse.deserialize(data)
            data.pop("method")
            return implementation(**data)
        else:
            raise RouteConfigurationError('Missing field "method" of Auth.')


class NoAuth(Auth):
    """Placeholder authentication method. Doesn't perform authentication."""

    method = None

    def authenticate(self, request: IncomingRequest) -> None:
        """Authenticate IncomingRequest. Always succeds."""
        return None

    def serialize(self) -> None:
        """Convert Auth to json value."""
        return None


class AuthWithResponse(Auth, abc.ABC):
    """Authentication method with configured error response."""

    def __init__(self, unauthorized_response: Response):
        self.unauthorized_response = unauthorized_response

    def serialize(self) -> Dict[str, Any]:
        """Convert Auth to json value."""
        return {
            "method": self.method,
            "unauthorized_response": self.unauthorized_response.serialize(),
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> Auth:
        """Convert json value to Auth."""
        if "method" in data:
            implementation = cls._find_implementation(data["method"])
            data.pop("method")
            if response_data := data.pop("unauthorized_response", None):
                response = Response.deserialize(response_data)
            else:
                response = Response(
                    {"error": "Unauthorized", "message": "Authentication failed."},
                    Delay(0.0),
                    status=401,
                )
            return implementation(response, **data)
        else:
            raise RouteConfigurationError('Missing field "method" of Auth.')


class TokenAuth(AuthWithResponse):
    """Authentication using http token in header."""

    method = "token"

    def __init__(self, unauthorized_response: Response, token: str):
        super().__init__(unauthorized_response)
        self.token = token

    def _get_header(self, request: IncomingRequest) -> str:
        """Get value of http header containing authentication token."""
        header = request.headers.get("Authorization")
        if not header:
            raise AuthenticationError('Missing authentication header "Authorization".')
        return header

    def _get_token(self, header: str) -> str:
        """Get authetication token from http header."""
        match = re.match(r"Bearer (?P<token>.*)", header)
        if not match:
            raise AuthenticationError(f"Invalid authentication header {header}.")

        return match["token"]

    def authenticate(self, request: IncomingRequest) -> None:
        """Check if IncomingRequest contains valid token authentication, raise exception if not."""
        header = self._get_header(request)
        token = self._get_token(header)
        if token != self.token:
            raise AuthenticationError(
                f"Authentication token {token} doens't match {self.token}."
            )

    def serialize(self) -> Dict[str, str]:
        """Convert TokenAuth to json value."""
        data = super().serialize()
        data.update({"token": self.token})
        return data


class BasicAuth(AuthWithResponse):
    """Authentication using username and password in http header."""

    method = "basic"

    def __init__(self, unauthorized_response: Response, username: str, password: str):
        super().__init__(unauthorized_response)
        self.username = username
        self.password = password

    def _get_header(self, request: IncomingRequest) -> str:
        """Get string containing base64 string containting username and password."""
        token = request.headers.get("Authorization")
        if not token:
            raise AuthenticationError('Missing authentication header "Authorization".')
        return token

    def _get_username_password(self, token: str) -> Tuple[str, str]:
        """Parse base64 string to username and password."""
        try:
            return basicauth.decode(token)
        except basicauth.DecodeError:
            raise AuthenticationError(f"Invalid authentication header {token}.")

    def authenticate(self, request: IncomingRequest) -> None:
        """Check if IncomingRequest contains valid username and password, raise exception if not."""
        token = self._get_header(request)
        username, password = self._get_username_password(token)
        if username != self.username or password != self.password:
            raise AuthenticationError(
                f"Authentication {username}:{password} doens't match {self.username}:{self.password}."
            )

    def serialize(self) -> Dict[str, str]:
        """Convert BasicAuth to json value."""
        data = super().serialize()
        data.update(
            {
                "username": self.username,
                "password": self.password,
            }
        )
        return data


class HmacAuth(AuthWithResponse):
    """Authentication using hmac signature in url."""

    method = "hmac"

    def __init__(self, unauthorized_response: Response, key: str):
        super().__init__(unauthorized_response)
        self.key = key
        self.past_tolerance = 3600
        self.future_tolerance = 5

    def _hash_string(self, url: str) -> str:
        """Hash given URL using HMAC with SHA1 digest."""
        hash_maker = hmac.new(self.key.encode("utf-8"), digestmod=hashlib.sha1)
        hash_maker.update(url.encode("utf-8"))
        return hash_maker.hexdigest()

    def _get_timestamp(self, args: Dict[str, str]) -> datetime.datetime:
        """Get timestamp from url."""
        if "hmac_timestamp" not in args:
            raise AuthenticationError(
                'HMAC authentication failed, URL is missing required parameter: "hmac_timestamp".'
            )
        return datetime.datetime.fromtimestamp(float(args["hmac_timestamp"]))

    def _get_signature(self, args: Dict[str, str]) -> str:
        """Get hmac signature from url."""
        if "hmac_sign" not in args:
            raise AuthenticationError(
                'HMAC authentication failed, URL is missing a required parameter: "hmac_sign".'
            )
        return args["hmac_sign"]

    def _check_time(self, timestamp: datetime.datetime) -> None:
        """Check if given timestamp is within allowed bound."""
        now = datetime.datetime.now()

        if timestamp > now + datetime.timedelta(seconds=self.future_tolerance):
            raise AuthenticationError(
                f"HMAC authentication failed, URL contains hmac_timestamp "
                f"more than {self.future_tolerance} seconds in the future: {timestamp}"
            )

        if timestamp < now - datetime.timedelta(seconds=self.past_tolerance):
            raise AuthenticationError(
                f"HMAC authentication failed, URL contains hmac_timestamp "
                f"more than {self.past_tolerance} seconds in the past: {timestamp}"
            )

    def _hash_url(self, url: str, query: str) -> str:
        """Calculate hash of used url using the hmac key."""
        parsed_url = urllib.parse.urlparse(url)
        hashable_url = parsed_url.path + "?" + re.sub(r"&hmac_sign=.*$", "", query)
        return self._hash_string(hashable_url)

    def _check_signature(self, url_hash: str, signature: str) -> None:
        """Check if signature matches expected hash."""
        if not url_hash or url_hash != signature:
            raise AuthenticationError(
                'HMAC authentication failed, hash in URL parameter "hmac_sign" is invalid.'
            )

    def authenticate(self, request: IncomingRequest) -> None:
        """Check if IncomingRequest contains valid authentication, raise exception if not."""
        timestamp = self._get_timestamp(request.args)
        signature = self._get_signature(request.args)
        url_hash = self._hash_url(request.url, request.query_string)

        self._check_signature(url_hash, signature)
        self._check_time(timestamp)

    def serialize(self) -> Dict[str, str]:
        """Convert Auth to json value."""
        data = super().serialize()
        data.update({"key": self.key})
        return data


class FormAuth(AuthWithResponse):
    """Authentication using form data."""

    method = "form"

    def __init__(self, unauthorized_response: Response, fields: Dict[str, str]):
        super().__init__(unauthorized_response)
        self.fields = fields

    def _get_field(self, form: Dict[str, str], field: str) -> str:
        """Get value of form field."""
        if field not in form:
            raise AuthenticationError(f'Missing authentication field "{field}".')
        return form[field]

    def authenticate(self, request: IncomingRequest) -> None:
        """Check if IncomingRequest contains valid authentication, raise exception if not."""
        for field, value in self.fields.items():
            sent_value = self._get_field(request.form, field)
            if value != sent_value:
                raise AuthenticationError(
                    f'Incorrect value "{sent_value}" in field "{field}", expected "{value}".'
                )

    def serialize(self) -> Dict[str, str]:
        """Convert Auth to json value."""
        data = super().serialize()
        data.update({"fields": self.fields})
        return data


class CookieAuth(AuthWithResponse):
    """Authentication using http cookie."""

    method = "cookie"

    def __init__(self, unauthorized_response: Response, name: str, value: str):
        super().__init__(unauthorized_response)
        self.name = name
        self.value = value

    def _get_cookie(self, cookies: Dict[str, str]) -> str:
        """Get value of cookie."""
        if self.name not in cookies:
            raise AuthenticationError(f'Missing authentication cookie "{self.name}".')
        return cookies[self.name]

    def authenticate(self, request: IncomingRequest) -> None:
        """Check if IncomingRequest contains valid authentication, raise exception if not."""
        sent_value = self._get_cookie(request.cookies)
        if self.value != sent_value:
            raise AuthenticationError(
                f'Incorrect value "{sent_value}" of cookie "{self.name}", expected "{self.value}".'
            )

    def serialize(self) -> Dict[str, str]:
        """Convert Auth to json value."""
        data = super().serialize()
        data.update({"name": self.name, "value": self.value})
        return data
