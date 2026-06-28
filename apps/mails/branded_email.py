"""Shared branded email layout — mirrors frontend/src/app/globals.css tokens."""

from __future__ import annotations

from html import escape

from django.conf import settings
from django.utils import timezone

BRAND_EMERALD = '#45a874'
BRAND_DARK = '#193e32'
BRAND_LIGHT_BG = '#f4f8f6'
PRIMARY = '#1161fe'
FOREGROUND = '#171717'
MUTED = '#6b7280'
BORDER = '#e5e7eb'
SURFACE = '#ffffff'
SURFACE_LOW = '#f9fafb'


def app_name() -> str:
    return getattr(settings, 'APP_NAME', 'Sajilowork')


def cta_button(href: str, label: str) -> str:
    safe_href = escape(href, quote=True)
    safe_label = escape(label)
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px 0 20px;">
  <tr>
    <td align="center">
      <a href="{safe_href}" style="display:inline-block;padding:14px 32px;background-color:{BRAND_EMERALD};color:#ffffff;font-size:15px;font-weight:700;text-decoration:none;border-radius:10px;box-shadow:0 4px 14px rgba(69,168,116,0.35);">
        {safe_label}
      </a>
    </td>
  </tr>
</table>"""


def fallback_link(href: str) -> str:
    safe_href = escape(href)
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:20px;">
  <tr>
    <td style="padding:14px 16px;background-color:{SURFACE_LOW};border:1px solid {BORDER};border-radius:10px;">
      <p style="margin:0 0 6px;font-size:11px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{MUTED};">
        Or copy this link
      </p>
      <p style="margin:0;font-size:12px;line-height:1.6;color:{PRIMARY};word-break:break-all;font-family:ui-monospace,'Cascadia Code',Consolas,monospace;">
        {safe_href}
      </p>
    </td>
  </tr>
</table>"""


def notice_box(text: str, *, tone: str = 'info') -> str:
    safe_text = escape(text)
    if tone == 'warning':
        bg = '#fff7ed'
        border_color = '#fed7aa'
        text_color = '#9a3412'
    else:
        bg = SURFACE_LOW
        border_color = BORDER
        text_color = MUTED
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:20px;">
  <tr>
    <td style="padding:14px 16px;background-color:{bg};border:1px solid {border_color};border-radius:10px;">
      <p style="margin:0;font-size:13px;line-height:1.6;color:{text_color};">{safe_text}</p>
    </td>
  </tr>
</table>"""


def render_branded_email(
    *,
    page_title: str,
    eyebrow: str,
    headline: str,
    intro: str,
    body_html: str,
    footer_note: str = '',
) -> str:
    app = escape(app_name())
    safe_page_title = escape(page_title)
    safe_eyebrow = escape(eyebrow)
    safe_headline = escape(headline)
    safe_intro = escape(intro)
    safe_footer = escape(footer_note) if footer_note else f'This email was sent by {app}.'
    year = timezone.now().year

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>{safe_page_title}</title>
</head>
<body style="margin:0;padding:0;background-color:{BRAND_LIGHT_BG};font-family:Manrope,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:{BRAND_LIGHT_BG};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">
          <tr>
            <td style="background-color:{BRAND_DARK};border-radius:16px 16px 0 0;padding:28px 32px 24px;">
              <p style="margin:0 0 8px;font-size:12px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{BRAND_EMERALD};">
                {safe_eyebrow}
              </p>
              <h1 style="margin:0;font-family:Outfit,'Segoe UI',sans-serif;font-size:26px;font-weight:700;line-height:1.25;color:#ffffff;">
                {safe_headline}
              </h1>
              <p style="margin:10px 0 0;font-size:15px;line-height:1.5;color:rgba(255,255,255,0.82);">
                {safe_intro}
              </p>
            </td>
          </tr>
          <tr>
            <td style="height:4px;background:linear-gradient(90deg,{BRAND_EMERALD} 0%,{PRIMARY} 100%);font-size:0;line-height:0;">&nbsp;</td>
          </tr>
          <tr>
            <td style="background-color:{SURFACE};border:1px solid {BORDER};border-top:none;border-radius:0 0 16px 16px;padding:28px 32px 24px;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:20px 8px 0;text-align:center;">
              <p style="margin:0 0 6px;font-size:12px;line-height:1.5;color:{MUTED};">{safe_footer}</p>
              <p style="margin:0;font-size:12px;color:{MUTED};">&copy; {year} {app}. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
