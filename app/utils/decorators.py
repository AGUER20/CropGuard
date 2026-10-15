"""Role-based access control helpers (3.8: "different access levels for
the different types of users")."""
from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*allowed_roles):
    """Restrict a route to users whose `.role` is in allowed_roles.

    Also blocks researcher accounts that are awaiting admin approval,
    matching the elevated-access-by-approval flow described for
    researchers/agricultural officers.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.role not in allowed_roles:
                abort(403)
            if current_user.role == "researcher" and not current_user.is_approved:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def allowed_file(filename, allowed_extensions):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_extensions
    )
