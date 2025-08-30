from rest_framework.exceptions import ErrorDetail

def extract_error_message(e):
    """
    Extracts a user-friendly error message from various exception types.
    """
    error_message = str(e)
    if hasattr(e, 'detail'):
        detail = e.detail
        if isinstance(detail, (list, dict)):
            # Flatten list/dict to string
            error_message = (
                detail[0] if isinstance(detail, list) and detail else
                next(iter(detail.values()))[0] if isinstance(detail, dict) and detail else str(detail)
            )
        elif isinstance(detail, ErrorDetail):
            error_message = str(detail)
        else:
            error_message = str(detail)
    elif isinstance(e, ErrorDetail):
        error_message = str(e)
    return error_message
