"""
Temporary patch for Django compatibility with Python 3.14
This fixes multiple compatibility issues:
1. 'super' object has no attribute 'dicts' error
2. 'RequestContext' object has no attribute 'template' error
3. 'RequestContext' object has no attribute 'autoescape' error
"""
from django.template import context as template_context
from django.template.context import RenderContext


# Store the original __copy__ methods
_original_base_copy = template_context.BaseContext.__copy__
_original_request_copy = template_context.RequestContext.__copy__


def patched_base_copy(self):
    """
    Patched __copy__ method for BaseContext that works with Python 3.14
    Copies all instance attributes to avoid missing attribute errors
    """
    duplicate = object.__new__(self.__class__)
    
    # Copy all attributes from self to duplicate
    for attr in ['dicts', 'template', 'autoescape', 'use_l10n', 'use_tz']:
        if hasattr(self, attr):
            setattr(duplicate, attr, getattr(self, attr))
    
    # Special handling for dicts - make a copy of the list
    if hasattr(self, 'dicts'):
        duplicate.dicts = self.dicts[:]
    
    # Initialize render_context
    if hasattr(self, 'render_context'):
        duplicate.render_context = RenderContext()
    else:
        duplicate.render_context = RenderContext()
    
    return duplicate


def patched_request_copy(self):
    """
    Patched __copy__ method for RequestContext that works with Python 3.14
    Copies all instance attributes to avoid missing attribute errors
    """
    duplicate = object.__new__(self.__class__)
    
    # Copy all standard attributes
    for attr in ['dicts', 'request', '_processors', '_processors_index', 
                 'template', 'autoescape', 'use_l10n', 'use_tz']:
        if hasattr(self, attr):
            setattr(duplicate, attr, getattr(self, attr))
    
    # Special handling for dicts - make a copy of the list
    if hasattr(self, 'dicts'):
        duplicate.dicts = self.dicts[:]
    
    # Initialize render_context
    duplicate.render_context = RenderContext()
    
    return duplicate


# Apply the patches
template_context.BaseContext.__copy__ = patched_base_copy
template_context.RequestContext.__copy__ = patched_request_copy


# Patch the BaseContext and RequestContext __init__ to ensure all attributes exist
_original_base_init = template_context.BaseContext.__init__
_original_request_init = template_context.RequestContext.__init__


def patched_base_init(self, dict_=None):
    """
    Patched __init__ method for BaseContext to ensure all attributes exist
    """
    _original_base_init(self, dict_)
    # Ensure all expected attributes exist
    if not hasattr(self, 'template'):
        self.template = None
    if not hasattr(self, 'autoescape'):
        self.autoescape = True
    if not hasattr(self, 'use_l10n'):
        self.use_l10n = None
    if not hasattr(self, 'use_tz'):
        self.use_tz = None


def patched_request_init(self, request, dict_=None, processors=None, use_l10n=None, use_tz=None, autoescape=True):
    """
    Patched __init__ method for RequestContext to ensure all attributes exist
    """
    _original_request_init(self, request, dict_, processors, use_l10n, use_tz, autoescape)
    # Ensure all expected attributes exist
    if not hasattr(self, 'template'):
        self.template = None
    if not hasattr(self, 'autoescape'):
        self.autoescape = autoescape
    if not hasattr(self, 'use_l10n'):
        self.use_l10n = use_l10n
    if not hasattr(self, 'use_tz'):
        self.use_tz = use_tz


template_context.BaseContext.__init__ = patched_base_init
template_context.RequestContext.__init__ = patched_request_init
