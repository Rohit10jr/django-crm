import six 
from django.contrib.auth.tokens import PasswordResetTokenGenerator


class TokenGenerator(PasswordResetTokenGenerator):
"""This class is used to generate a unique token to identify the user"""

def _make_hash_value(self, user, timestamp):
    return (
        six.text_type(user.pk)
        + six.text_type(timestamp)
        + six.text_type(user.is_active)
    )


account_acitvation_token = TokenGenerator()