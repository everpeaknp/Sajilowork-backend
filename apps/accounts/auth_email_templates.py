"""Branded HTML + plain-text templates for auth emails (password reset, verification)."""

from __future__ import annotations

from html import escape

from apps.mails.branded_email import (
    FOREGROUND,
    MUTED,
    app_name,
    cta_button,
    fallback_link,
    notice_box,
    render_branded_email,
)


def _greeting(display_name: str) -> str:
    safe_name = escape(display_name)
    return f"""
<p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:{FOREGROUND};">
  Hi <strong>{safe_name}</strong>,
</p>"""


def build_password_reset_subject() -> str:
    return f'Reset your {app_name()} password'


def build_password_reset_text(*, display_name: str, link: str) -> str:
    app = app_name()
    return (
        f'Hi {display_name},\n\n'
        'You requested a password reset. Open the link below to choose a new password:\n\n'
        f'{link}\n\n'
        'This link expires in 24 hours. If you did not request this, you can ignore this email.\n\n'
        f'— {app}'
    )


def build_password_reset_html(*, display_name: str, link: str) -> str:
    body = (
        _greeting(display_name)
        + f"""
<p style="margin:0 0 4px;font-size:15px;line-height:1.65;color:{FOREGROUND};">
  We received a request to reset the password for your {escape(app_name())} account.
  Click the button below to choose a new password.
</p>"""
        + cta_button(link, 'Reset password')
        + notice_box(
            'This link expires in 24 hours. If you did not request a password reset, '
            'you can safely ignore this email — your password will stay the same.',
            tone='warning',
        )
        + fallback_link(link)
    )
    return render_branded_email(
        page_title='Reset your password',
        eyebrow='Account security',
        headline='Reset your password',
        intro='Choose a new password to regain access to your account.',
        body_html=body,
        footer_note=f'You received this because a password reset was requested on {escape(app_name())}.',
    )


def build_email_verification_subject() -> str:
    return f'Verify your {app_name()} email'


def build_email_verification_text(*, display_name: str, link: str) -> str:
    app = app_name()
    return (
        f'Hi {display_name},\n\n'
        'Thanks for signing up. Please verify your email address by opening this link:\n\n'
        f'{link}\n\n'
        'This link expires in 3 days. If you did not create an account, you can ignore this email.\n\n'
        f'— {app}'
    )


def build_email_verification_html(*, display_name: str, link: str) -> str:
    body = (
        _greeting(display_name)
        + f"""
<p style="margin:0 0 4px;font-size:15px;line-height:1.65;color:{FOREGROUND};">
  Thanks for joining {escape(app_name())}! Please confirm your email address so we can
  keep your account secure and send you important updates.
</p>"""
        + cta_button(link, 'Verify email address')
        + notice_box(
            'This link expires in 3 days. If you did not create an account, '
            'you can safely ignore this email.',
        )
        + fallback_link(link)
    )
    return render_branded_email(
        page_title='Verify your email',
        eyebrow='Welcome',
        headline='Verify your email',
        intro='One quick step to activate your account.',
        body_html=body,
        footer_note=f'You received this because someone signed up on {escape(app_name())} with this email.',
    )
