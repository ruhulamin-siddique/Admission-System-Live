"""
CoE Module — Template Tags & Filters
Includes WhatsApp Click-to-Chat URL normalizer and button generators.
"""

from django import template
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter(name='whatsapp_url')
def whatsapp_url(phone_number, text=None):
    """
    Normalizes Bangladeshi mobile/phone number into a valid WhatsApp Click-to-Chat URL.
    Example: '01712345678' -> 'https://wa.me/8801712345678'
    Example with text: 'https://wa.me/8801712345678?text=Hello...'
    """
    if not phone_number:
        return ''
    
    # Strip spaces, dashes, parentheses, plus signs
    digits = re.sub(r'[^\d]', '', str(phone_number))
    
    if not digits:
        return ''
    
    # Normalize Bangladeshi numbers
    if digits.startswith('880') and len(digits) == 13:
        wa_number = digits
    elif digits.startswith('88') and len(digits) == 12:
        wa_number = digits
    elif digits.startswith('01') and len(digits) == 11:
        wa_number = '88' + digits
    else:
        wa_number = digits

    base_url = f"https://wa.me/{wa_number}"
    
    if text:
        params = urlencode({'text': str(text)})
        return f"{base_url}?{params}"
    
    return base_url


@register.simple_tag
def whatsapp_btn(phone_number, text=None, label=None, css_class="btn btn-sm text-white font-weight-bold shadow-sm px-2.5 py-1"):
    """
    Renders a WhatsApp Click-to-Chat button link with official WhatsApp branding.
    """
    url = whatsapp_url(phone_number, text)
    if not url:
        return ''
    
    label_html = f'<span class="ml-1">{label}</span>' if label else ''
    style = 'background:#25D366; border:none; border-radius:20px; font-size:0.78rem; display:inline-flex; align-items:center; color:#ffffff !important; text-decoration:none;'
    
    html = f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="{css_class}" style="{style}" title="Chat on WhatsApp"><i class="fab fa-whatsapp" style="font-size:0.9rem;"></i>{label_html}</a>'
    return mark_safe(html)
