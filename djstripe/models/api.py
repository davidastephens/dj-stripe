import re
from base64 import b64encode
from uuid import uuid4

from django.core.validators import RegexValidator
from django.db import models

from ..enums import APIKeyType
from ..fields import StripeEnumField
from .base import StripeModel

# A regex to validate API key format
API_KEY_REGEX = r"^(pk|sk|rk)_(test|live)_([a-zA-Z0-9]{24,99})"


def generate_api_key_id() -> str:
    b64_id = b64encode(uuid4().bytes).decode()
    generated_id = b64_id.rstrip("=").replace("+", "").replace("/", "")
    return f"djstripe_mk_{generated_id}"


def get_api_key_details_by_prefix(api_key: str):
    sre = re.match(API_KEY_REGEX, api_key)
    if not sre:
        raise ValueError(f"Invalid API key: {api_key!r}")

    key_type = {
        "pk": APIKeyType.publishable,
        "sk": APIKeyType.secret,
        "rk": APIKeyType.restricted,
    }.get(sre.group(1), "")
    livemode = {"test": False, "live": True}.get(sre.group(2))

    return key_type, livemode


class APIKeyManager(models.Manager):
    def get_or_create_by_api_key(self, secret: str):
        key_type, livemode = get_api_key_details_by_prefix(secret)
        return super().get_or_create(
            secret=secret, defaults={"type": key_type, "livemode": livemode}
        )


class APIKey(StripeModel):
    object = "api_key"

    id = models.CharField(max_length=255, default=generate_api_key_id, editable=False)
    type = StripeEnumField(enum=APIKeyType)
    name = models.CharField("Key name", max_length=100, blank=True)
    secret = models.CharField(
        max_length=128, validators=[RegexValidator(regex=API_KEY_REGEX)], unique=True
    )

    objects = APIKeyManager()

    def get_stripe_dashboard_url(self):
        return self._get_base_stripe_dashboard_url() + "apikeys"

    def __str__(self):
        return self.name or self.secret_redacted

    @property
    def secret_redacted(self) -> str:
        """
        Returns a redacted version of the secret, suitable for display purposes.

        Same algorithm used on the Stripe dashboard.
        """
        secret_prefix, _, secret_part = self.secret.rpartition("_")
        secret_part = secret_part[-4:]
        return f"{secret_prefix}_...{secret_part}"