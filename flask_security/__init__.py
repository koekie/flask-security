# -*- coding: utf-8 -*-
"""
    flask_security
    ~~~~~~~~~~~~~~

    Flask-Security is a Flask extension that aims to add quick and simple
    security via Flask-Login, Flask-Principal, Flask-WTF, and passlib.

    :copyright: (c) 2012-2019 by Matt Wright.
    :copyright: (c) 2019 by J. Christopher Wagner.
    :license: MIT, see LICENSE for more details.
"""

# flake8: noqa: F401

from .core import Security, RoleMixin, UserMixin, AnonymousUser, current_user
from .datastore import (
    UserDatastore,
    SQLAlchemyUserDatastore,
    MongoEngineUserDatastore,
    PeeweeUserDatastore,
    PonyUserDatastore,
    SQLAlchemySessionUserDatastore,
)
from .decorators import (
    auth_token_required,
    anonymous_user_required,
    handle_csrf,
    http_auth_required,
    login_required,
    roles_accepted,
    roles_required,
    auth_required,
    permissions_accepted,
    permissions_required,
    unauth_csrf,
)
from .forms import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    RegisterForm,
    ResetPasswordForm,
    PasswordlessLoginForm,
    ConfirmRegisterForm,
    SendConfirmationForm,
    TwoFactorRescueForm,
    TwoFactorSetupForm,
    TwoFactorVerifyCodeForm,
    TwoFactorVerifyPasswordForm,
)
from .models import fsqla
from .signals import (
    confirm_instructions_sent,
    login_instructions_sent,
    password_changed,
    password_reset,
    reset_password_instructions_sent,
    tf_code_confirmed,
    tf_profile_changed,
    tf_security_token_sent,
    tf_disabled,
    user_confirmed,
    user_registered,
)
from .utils import (
    FsJsonEncoder,
    SmsSenderBaseClass,
    SmsSenderFactory,
    get_hmac,
    get_token_status,
    get_url,
    hash_password,
    login_user,
    logout_user,
    send_mail,
    transform_url,
    url_for_security,
    verify_password,
    verify_and_update_password,
)

__version__ = "3.3.0rc3"
__all__ = (
    "AnonymousUser",
    "ConfirmRegisterForm",
    "ForgotPasswordForm",
    "LoginForm",
    "MongoEngineUserDatastore",
    "PasswordlessLoginForm",
    "PeeweeUserDatastore",
    "PonyUserDatastore",
    "RegisterForm",
    "ResetPasswordForm",
    "RoleMixin",
    "SQLAlchemyUserDatastore",
    "SQLAlchemySessionUserDatastore",
    "Security",
    "UserMixin",
    "anonymous_user_required",
    "auth_required",
    "auth_token_required",
    "confirm_instructions_sent",
    "current_user",
    "handle_csrf",
    "http_auth_required",
    "login_required",
    "login_user",
    "logout_user",
    "password_reset",
    "permissions_required",
    "permissions_accepted",
    "reset_password_instructions_sent",
    "roles_accepted",
    "roles_required",
    "unauth_csrf",
    "url_for_security",
    "user_confirmed",
    "user_registered",
)
