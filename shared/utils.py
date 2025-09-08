from rest_framework.exceptions import ErrorDetail

def extract_error_message(e):
    """
    Extracts a user-friendly error message from various exception types.
    Handles 'non_field_errors' in dict details.
    """
    error_message = str(e)
    if hasattr(e, 'detail'):
        detail = e.detail
        if isinstance(detail, dict):
            if "non_field_errors" in detail and detail["non_field_errors"]:
                error_message = detail["non_field_errors"] if isinstance(detail["non_field_errors"], list) else [detail["non_field_errors"]]
            else:
                # # Fallback to first value in dict
                # error_message = next(iter(detail.values())) if detail else str(detail)
                error_dict = {k: v[0] if isinstance(v, list) and v else str(v) for k, v in detail.items()}
                error_message = [error_dict]
        elif isinstance(detail, list):
            error_message = detail if detail else str(detail)
        elif isinstance(detail, ErrorDetail):
            error_message = str(detail)
        else:
            error_message = str(detail)
    elif isinstance(e, ErrorDetail):
        error_message = str(e)
    return error_message
