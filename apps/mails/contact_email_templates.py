"""Branded HTML + plain-text templates for contact form admin notifications."""

from __future__ import annotations

from html import escape

from django.utils import timezone
from django.utils.formats import date_format

from apps.mails.branded_email import (
    BRAND_DARK,
    BRAND_EMERALD,
    BRAND_LIGHT_BG,
    BORDER,
    FOREGROUND,
    MUTED,
    PRIMARY,
    SURFACE,
    SURFACE_LOW,
    app_name,
    render_branded_email,
)


def _format_submitted_at(value) -> str:
    if value is None:
        return 'N/A'
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return date_format(value, 'N j, Y, P')


def build_contact_submission_subject(name: str) -> str:
    return f'New contact form submission from {name}'


def build_contact_submission_text(
    *,
    name: str,
    email: str,
    message: str,
    submitted_at,
    ip_address: str | None,
) -> str:
    lines = [
        f'New contact form submission — {app_name()}',
        '',
        f'Name: {name}',
        f'Email: {email}',
        '',
        'Message:',
        message,
        '',
        '—' * 40,
        f'Submitted: {_format_submitted_at(submitted_at)}',
        f'IP address: {ip_address or "N/A"}',
        '',
        f'Reply directly to {email} to respond to this inquiry.',
    ]
    return '\n'.join(lines)


def build_contact_submission_html(
    *,
    name: str,
    email: str,
    message: str,
    submitted_at,
    ip_address: str | None,
) -> str:
    safe_name = escape(name)
    safe_email = escape(email)
    safe_message = escape(message).replace('\n', '<br />')
    safe_ip = escape(ip_address or 'N/A')
    safe_submitted = escape(_format_submitted_at(submitted_at))
    mailto = f'mailto:{escape(email)}'

    body_html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
  <tr>
    <td style="width:48px;vertical-align:top;padding-right:14px;">
      <div style="width:48px;height:48px;border-radius:9999px;background-color:{BRAND_LIGHT_BG};border:2px solid {BRAND_EMERALD};text-align:center;line-height:44px;font-family:Outfit,sans-serif;font-size:20px;font-weight:700;color:{BRAND_DARK};">
        {safe_name[:1].upper()}
      </div>
    </td>
    <td style="vertical-align:top;">
      <p style="margin:0;font-size:18px;font-weight:700;color:{FOREGROUND};">{safe_name}</p>
      <p style="margin:4px 0 0;font-size:14px;color:{MUTED};">
        <a href="{mailto}" style="color:{PRIMARY};text-decoration:none;font-weight:600;">{safe_email}</a>
      </p>
    </td>
    <td align="right" style="vertical-align:top;">
      <a href="{mailto}" style="display:inline-block;padding:10px 18px;background-color:{BRAND_EMERALD};color:#ffffff;font-size:13px;font-weight:600;text-decoration:none;border-radius:8px;">
        Reply
      </a>
    </td>
  </tr>
</table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">
  <tr>
    <td style="padding:14px 16px;background-color:{SURFACE_LOW};border:1px solid {BORDER};border-radius:12px 12px 0 0;">
      <p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{MUTED};">Name</p>
      <p style="margin:0;font-size:15px;font-weight:600;color:{FOREGROUND};">{safe_name}</p>
    </td>
  </tr>
  <tr>
    <td style="padding:14px 16px;background-color:{SURFACE};border:1px solid {BORDER};border-top:none;">
      <p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{MUTED};">Email</p>
      <p style="margin:0;font-size:15px;color:{FOREGROUND};">
        <a href="{mailto}" style="color:{PRIMARY};text-decoration:none;font-weight:600;">{safe_email}</a>
      </p>
    </td>
  </tr>
  <tr>
    <td style="padding:16px;background-color:{SURFACE_LOW};border:1px solid {BORDER};border-top:none;border-radius:0 0 12px 12px;">
      <p style="margin:0 0 8px;font-size:11px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{MUTED};">Message</p>
      <p style="margin:0;font-size:15px;line-height:1.65;color:{FOREGROUND};">{safe_message}</p>
    </td>
  </tr>
</table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:1px solid {BORDER};padding-top:18px;">
  <tr>
    <td style="padding:0 8px 0 0;vertical-align:top;width:50%;">
      <p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{MUTED};">Submitted</p>
      <p style="margin:0;font-size:13px;color:{FOREGROUND};">{safe_submitted}</p>
    </td>
    <td style="padding:0 0 0 8px;vertical-align:top;width:50%;">
      <p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{MUTED};">IP address</p>
      <p style="margin:0;font-size:13px;color:{FOREGROUND};font-family:ui-monospace,'Cascadia Code',Consolas,monospace;">{safe_ip}</p>
    </td>
  </tr>
</table>"""

    return render_branded_email(
        page_title='New contact form submission',
        eyebrow='Contact inbox',
        headline='New message received',
        intro=f'Someone reached out through the {escape(app_name())} contact form.',
        body_html=body_html,
        footer_note=f'This notification was sent from the {escape(app_name())} contact form.',
    )
