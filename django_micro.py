import inspect
import os
import sys

import django
from django.conf import settings
from django.conf.urls import url
from django.core import management
from django.template import Library
from django.core.exceptions import ImproperlyConfigured

__all__ = ['command', 'configure', 'run', 'route', 'template']

# use parent directory as root import path
sys.path[0] = os.path.abspath('..')


# -------------------
# Application module
# -------------------

_app_module = None
_app_label = None


def _setup_module():
    app_module = sys.modules[inspect.stack()[2][0].f_locals['__name__']]
    app_label = os.path.basename(os.path.dirname(os.path.abspath(app_module.__file__)))
    file_name = app_module.__file__.split('.')[0]

    # register __main__ module as named module for import it without recursion
    sys.modules['{}.{}'.format(app_label, file_name)] = app_module

    # allow relative imports for app.py
    app_module.__package__ = app_label

    globals().update(_app_module=app_module, _app_label=app_label)


def get_app_label():
    if not _app_label:
        raise ImproperlyConfigured(
            "Application label is not detected. "
            "Check whether the configure() was called.")
    return _app_label


# -------------------
# Views and routes
# -------------------

urlpatterns = []


def route(pattern, view_func=None, *args, **kwargs):
    def decorator(view_func):
        if hasattr(view_func, 'as_view'):
            view_func = view_func.as_view()
        urlpatterns.append(url(pattern, view_func, *args, **kwargs))
        return view_func

    # allow use decorator directly
    # route(r'^$', show_index)
    if view_func:
        return decorator(view_func)

    return decorator


# -------------------
# Template tags
# -------------------

register = template = Library()


# --------------------
# Configuration
# --------------------

def configure(config_dict={}):
    _setup_module()  # find in the stack module that calls this function
    config_dict.setdefault('TEMPLATE_DIRS', ['templates'])

    kwargs = {
        'INSTALLED_APPS': [_app_label] + config_dict.pop('INSTALLED_APPS', []),
        'ROOT_URLCONF': __name__,
        'TEMPLATES': [{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': config_dict.pop('TEMPLATE_DIRS'),
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': config_dict.pop('CONTEXT_PROCESSORS', []),
                'builtins': [__name__],
            },
        }],
    }

    kwargs.update({key: val for key, val in config_dict.items() if key.isupper()})
    settings.configure(**kwargs)
    django.setup()


# --------------------
# Management commands
# --------------------

_commands = {}


def patch_get_commands():
    django_get_commands = management.get_commands

    def patched_get_commands():
        commands = django_get_commands()
        commands.update(_commands)
        return commands

    patched_get_commands.patched = True
    management.get_commands = patched_get_commands


def command(name, command_cls=None):
    if not getattr(management.get_commands, 'patched', False):
        patch_get_commands()

    def decorator(command_cls):
        command_instance = command_cls()
        # very dirty hack for extracting app name
        # from command (via https://goo.gl/1c1Irj)
        command_instance.rpartition = lambda x: [_app_label]
        _commands[name] = command_instance
        return command_cls

    # allow use decorator directly
    # command('print_hello', PrintHelloCommand)
    if command_cls:
        return decorator(command_cls)

    return decorator


# --------------------
# Bootstrap
# --------------------

def run():
    if not settings.configured:
        raise ImproperlyConfigured("You should call configure() after configuration define.")

    if _app_module.__name__ == '__main__':
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
    else:
        from django.core.wsgi import get_wsgi_application
        return get_wsgi_application()
