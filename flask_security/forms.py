# -*- coding: utf-8 -*-
"""
    flask_security.forms
    ~~~~~~~~~~~~~~~~~~~~

    Flask-Security forms module

    :copyright: (c) 2012 by Matt Wright.
    :copyright: (c) 2017 by CERN.
    :copyright: (c) 2019 by J. Christopher Wagner (jwag).
    :license: MIT, see LICENSE for more details.
"""

import inspect

from flask import Markup, current_app, request
from flask_login import current_user
from flask_wtf import FlaskForm as BaseForm
from speaklater import is_lazy_string, make_lazy_string
from wtforms import (
    BooleanField,
    Field,
    HiddenField,
    PasswordField,
    RadioField,
    StringField,
    SubmitField,
    ValidationError,
    validators,
)

from .confirmable import requires_confirmation
from .utils import (
    _,
    _datastore,
    config_value,
    do_flash,
    get_message,
    hash_password,
    localize_callback,
    url_for_security,
    validate_redirect_url,
)
from .twofactor import verify_totp

_default_field_labels = {
    "email": _("Email Address"),
    "password": _("Password"),
    "remember_me": _("Remember Me"),
    "login": _("Login"),
    "register": _("Register"),
    "send_confirmation": _("Resend Confirmation Instructions"),
    "recover_password": _("Recover Password"),
    "reset_password": _("Reset Password"),
    "retype_password": _("Retype Password"),
    "new_password": _("New Password"),
    "change_password": _("Change Password"),
    "send_login_link": _("Send Login Link"),
    "verify_password": _("Verify Password"),
    "change_method": _("Change Method"),
    "phone": _("Phone Number"),
    "code": _("Authentication Code"),
}


class ValidatorMixin(object):
    """
    This is called at import time - so there is no app context.
    Validators have state - namely self.message - but we need that
    xlated on a per-request basis. So we want a lazy_string - but we can't create
    that until we are in an app context.
    """

    def __init__(self, *args, **kwargs):
        # If the message is available from config[MSG_xx] then it can be xlated.
        # Otherwise it will be used as is.
        if "message" in kwargs:
            self._original_message = kwargs["message"]
            del kwargs["message"]
        else:
            self._original_message = None
        super(ValidatorMixin, self).__init__(*args, **kwargs)

    def __call__(self, form, field):
        if self._original_message and (
            not is_lazy_string(self.message) and not self.message
        ):
            # Creat on first usage within app context.
            cv = config_value("MSG_" + self._original_message)
            if cv:
                self.message = make_lazy_string(_local_xlate, cv[0])
            else:
                self.message = self._original_message
        return super(ValidatorMixin, self).__call__(form, field)


class EqualTo(ValidatorMixin, validators.EqualTo):
    pass


class Required(ValidatorMixin, validators.DataRequired):
    pass


class Email(ValidatorMixin, validators.Email):
    pass


class Length(ValidatorMixin, validators.Length):
    pass


email_required = Required(message="EMAIL_NOT_PROVIDED")
email_validator = Email(message="INVALID_EMAIL_ADDRESS")
password_required = Required(message="PASSWORD_NOT_PROVIDED")
password_length = Length(min=6, max=128, message="PASSWORD_INVALID_LENGTH")


def _local_xlate(text):
    """ LazyStrings need to be evaluated in the context of a request
    where _security.i18_domain is available.
    """
    return localize_callback(text)


def get_form_field_label(key):
    """ This is called during import since form fields are declared as part of
    class. Thus can't call 'localize_callback' until we need to actually
    translate/render form.
    """
    return make_lazy_string(_local_xlate, _default_field_labels.get(key, ""))


def unique_user_email(form, field):
    if _datastore.get_user(field.data) is not None:
        msg = get_message("EMAIL_ALREADY_ASSOCIATED", email=field.data)[0]
        raise ValidationError(msg)


def valid_user_email(form, field):
    form.user = _datastore.get_user(field.data)
    if form.user is None:
        raise ValidationError(get_message("USER_DOES_NOT_EXIST")[0])


class Form(BaseForm):
    def __init__(self, *args, **kwargs):
        if current_app.testing:
            self.TIME_LIMIT = None
        super(Form, self).__init__(*args, **kwargs)


class EmailFormMixin:
    email = StringField(
        get_form_field_label("email"), validators=[email_required, email_validator]
    )


class UserEmailFormMixin:
    user = None
    email = StringField(
        get_form_field_label("email"),
        validators=[email_required, email_validator, valid_user_email],
    )


class UniqueEmailFormMixin:
    email = StringField(
        get_form_field_label("email"),
        validators=[email_required, email_validator, unique_user_email],
    )


class PasswordFormMixin:
    password = PasswordField(
        get_form_field_label("password"), validators=[password_required]
    )


class NewPasswordFormMixin:
    password = PasswordField(
        get_form_field_label("password"),
        validators=[password_required, password_length],
    )


class PasswordConfirmFormMixin:
    password_confirm = PasswordField(
        get_form_field_label("retype_password"),
        validators=[
            EqualTo("password", message="RETYPE_PASSWORD_MISMATCH"),
            password_required,
        ],
    )


class NextFormMixin:
    next = HiddenField()

    def validate_next(self, field):
        if field.data and not validate_redirect_url(field.data):
            field.data = ""
            do_flash(*get_message("INVALID_REDIRECT"))
            raise ValidationError(get_message("INVALID_REDIRECT")[0])


class RegisterFormMixin:
    submit = SubmitField(get_form_field_label("register"))

    def to_dict(form):
        def is_field_and_user_attr(member):
            return isinstance(member, Field) and hasattr(
                _datastore.user_model, member.name
            )

        fields = inspect.getmembers(form, is_field_and_user_attr)
        return dict((key, value.data) for key, value in fields)


class SendConfirmationForm(Form, UserEmailFormMixin):
    """The default send confirmation form"""

    submit = SubmitField(get_form_field_label("send_confirmation"))

    def __init__(self, *args, **kwargs):
        super(SendConfirmationForm, self).__init__(*args, **kwargs)
        if request.method == "GET":
            self.email.data = request.args.get("email", None)

    def validate(self):
        if not super(SendConfirmationForm, self).validate():
            return False
        if self.user.confirmed_at is not None:
            self.email.errors.append(get_message("ALREADY_CONFIRMED")[0])
            return False
        return True


class ForgotPasswordForm(Form, UserEmailFormMixin):
    """The default forgot password form"""

    submit = SubmitField(get_form_field_label("recover_password"))

    def validate(self):
        if not super(ForgotPasswordForm, self).validate():
            return False
        if requires_confirmation(self.user):
            self.email.errors.append(get_message("CONFIRMATION_REQUIRED")[0])
            return False
        return True


class PasswordlessLoginForm(Form, UserEmailFormMixin):
    """The passwordless login form"""

    submit = SubmitField(get_form_field_label("send_login_link"))

    def __init__(self, *args, **kwargs):
        super(PasswordlessLoginForm, self).__init__(*args, **kwargs)

    def validate(self):
        if not super(PasswordlessLoginForm, self).validate():
            return False
        if not self.user.is_active:
            self.email.errors.append(get_message("DISABLED_ACCOUNT")[0])
            return False
        return True


class LoginForm(Form, NextFormMixin):
    """The default login form"""

    email = StringField(get_form_field_label("email"), validators=[email_required])
    password = PasswordField(
        get_form_field_label("password"), validators=[password_required]
    )
    remember = BooleanField(get_form_field_label("remember_me"))
    submit = SubmitField(get_form_field_label("login"))

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = request.args.get("next", "")
        self.remember.default = config_value("DEFAULT_REMEMBER_ME")
        if (
            current_app.extensions["security"].recoverable
            and not self.password.description
        ):
            html = Markup(
                u'<a href="{url}">{message}</a>'.format(
                    url=url_for_security("forgot_password"),
                    message=get_message("FORGOT_PASSWORD")[0],
                )
            )
            self.password.description = html

    def validate(self):
        if not super(LoginForm, self).validate():
            return False

        self.user = _datastore.get_user(self.email.data)

        if self.user is None:
            self.email.errors.append(get_message("USER_DOES_NOT_EXIST")[0])
            # Reduce timing variation between existing and non-existing users
            hash_password(self.password.data)
            return False
        if not self.user.password:
            self.password.errors.append(get_message("PASSWORD_NOT_SET")[0])
            # Reduce timing variation between existing and non-existing users
            hash_password(self.password.data)
            return False
        if not self.user.verify_and_update_password(self.password.data):
            self.password.errors.append(get_message("INVALID_PASSWORD")[0])
            return False
        if requires_confirmation(self.user):
            self.email.errors.append(get_message("CONFIRMATION_REQUIRED")[0])
            return False
        if not self.user.is_active:
            self.email.errors.append(get_message("DISABLED_ACCOUNT")[0])
            return False
        return True


class ConfirmRegisterForm(
    Form, RegisterFormMixin, UniqueEmailFormMixin, NewPasswordFormMixin
):
    pass


class RegisterForm(ConfirmRegisterForm, PasswordConfirmFormMixin, NextFormMixin):
    def __init__(self, *args, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)
        if not self.next.data:
            self.next.data = request.args.get("next", "")


class ResetPasswordForm(Form, NewPasswordFormMixin, PasswordConfirmFormMixin):
    """The default reset password form"""

    submit = SubmitField(get_form_field_label("reset_password"))


class ChangePasswordForm(Form, PasswordFormMixin):
    """The default change password form"""

    new_password = PasswordField(
        get_form_field_label("new_password"),
        validators=[password_required, password_length],
    )

    new_password_confirm = PasswordField(
        get_form_field_label("retype_password"),
        validators=[
            EqualTo("new_password", message="RETYPE_PASSWORD_MISMATCH"),
            password_required,
        ],
    )

    submit = SubmitField(get_form_field_label("change_password"))

    def validate(self):
        if not super(ChangePasswordForm, self).validate():
            return False

        if not current_user.verify_and_update_password(self.password.data):
            self.password.errors.append(get_message("INVALID_PASSWORD")[0])
            return False
        if self.password.data == self.new_password.data:
            self.password.errors.append(get_message("PASSWORD_IS_THE_SAME")[0])
            return False
        return True


class TwoFactorSetupForm(Form, UserEmailFormMixin):
    """The Two-factor token validation form"""

    setup = RadioField(
        "Available Methods",
        choices=[
            ("mail", "Set Up Using Mail"),
            ("google_authenticator", "Set Up Using Google Authenticator"),
            ("sms", "Set Up Using SMS"),
            ("disable", "Disable two factor authentication"),
        ],
    )
    phone = StringField(get_form_field_label("phone"))
    submit = SubmitField(get_form_field_label("submit"))

    def __init__(self, *args, **kwargs):
        super(TwoFactorSetupForm, self).__init__(*args, **kwargs)

    def validate(self):
        choices = config_value("TWO_FACTOR_ENABLED_METHODS")
        if not config_value("TWO_FACTOR_REQUIRED"):
            choices.append("disable")
        if "setup" not in self.data or self.data["setup"] not in choices:
            self.setup.errors = list()
            self.setup.errors.append(get_message("TWO_FACTOR_METHOD_NOT_AVAILABLE")[0])
            return False

        return True


class TwoFactorVerifyCodeForm(Form, UserEmailFormMixin):
    """The Two-factor token validation form"""

    code = StringField(get_form_field_label("code"))
    submit = SubmitField(get_form_field_label("submit code"))

    def __init__(self, *args, **kwargs):
        super(TwoFactorVerifyCodeForm, self).__init__(*args, **kwargs)

    def validate(self):
        # codes sent by sms or mail will be valid for another window cycle
        if self.primary_method == "google_authenticator":
            self.window = config_value("TWO_FACTOR_GOOGLE_AUTH_VALIDITY")
        elif self.primary_method == "mail":
            self.window = config_value("TWO_FACTOR_MAIL_VALIDITY")
        elif self.primary_method == "sms":
            self.window = config_value("TWO_FACTOR_SMS_VALIDITY")
        else:
            return False

        # verify entered token with user's totp secret
        if not verify_totp(
            token=self.code.data,
            totp_secret=self.user.tf_totp_secret,
            window=self.window,
        ):
            self.code.errors = list()
            self.code.errors.append(get_message("TWO_FACTOR_INVALID_TOKEN")[0])

            return False

        return True


class TwoFactorVerifyPasswordForm(Form, PasswordFormMixin):
    """The verify password form"""

    submit = SubmitField(get_form_field_label("verify_password"))

    def validate(self):
        if not super(TwoFactorVerifyPasswordForm, self).validate():
            return False

        self.user = current_user
        if not self.user.verify_and_update_password(self.password.data):
            self.password.errors.append(get_message("INVALID_PASSWORD")[0])
            return False

        return True


class TwoFactorRescueForm(Form, UserEmailFormMixin):
    """The Two-factor Rescue validation form """

    help_setup = RadioField(
        "Trouble Accessing Your Account?",
        choices=[
            ("lost_device", "Can not access mobile device?"),
            ("no_mail_access", "Can not access mail account?"),
        ],
    )
    submit = SubmitField(get_form_field_label("submit"))

    def __init__(self, *args, **kwargs):
        super(TwoFactorRescueForm, self).__init__(*args, **kwargs)

    def validate(self):
        return True
