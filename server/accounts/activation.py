"""One-time student QR activation tokens. Author: UniVerse Team."""
from django.core import signing
from django.utils.crypto import constant_time_compare

SALT = 'universe-student-activation-v1'
MAX_AGE_SECONDS = 180 * 24 * 60 * 60


def token_for(user):
    return signing.dumps({'user': user.pk, 'password': user.password[-16:]}, salt=SALT, compress=True)


def user_from_token(token):
    from django.contrib.auth.models import User
    payload = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    user = User.objects.select_related('guide_profile').get(pk=payload.get('user'), is_active=True)
    profile = getattr(user, 'guide_profile', None)
    if not profile or not profile.must_change_password or not constant_time_compare(payload.get('password', ''), user.password[-16:]):
        raise signing.BadSignature('Activation token is no longer valid.')
    return user
