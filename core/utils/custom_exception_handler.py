import logging
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.exceptions import ValidationError as DRFValidationError, ErrorDetail
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.response import Response
from rest_framework import status

# Setup logger
logger = logging.getLogger(__name__)


def normalize_error(detail):
    """
    Normalize any error detail into list[dict] format.
    """
    if isinstance(detail, list):
        # Example: ["This is an error"]
        return [{"error": str(v)} if not isinstance(v, dict) else v for v in detail]

    if isinstance(detail, dict):
        # Example: {"field": ["msg"], "other": ["msg2"]}
        return [{
            k: (v[0] if isinstance(v, list) and v else str(v))
            for k, v in detail.items()
        }]

    if isinstance(detail, ErrorDetail):
        return [{"error": str(detail)}]

    return [{"error": str(detail)}]


def custom_exception_handler(exc, context):
    """
    Global DRF exception handler that:
    - Normalizes errors into a consistent format
    - Handles both DRF and Django ValidationError
    - Logs unhandled server errors for debugging
    """

    request = context.get("request")

    # ✅ Handle Django ValidationError (model.clean(), save(), etc.)
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            detail = exc.message_dict  # {field: ["msg", ...]}
        elif hasattr(exc, "messages"):
            detail = exc.messages      # ["msg1", "msg2"]
        else:
            detail = str(exc)

        return Response(
            {"error": normalize_error(detail)},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ✅ Let DRF handle known API exceptions (serializer, auth, etc.)
    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = {"error": normalize_error(response.data)}
        return response

    # 🚨 Fallback: unhandled exception (500)
    logger.error(
        "Unhandled exception at %s %s: %s",
        request.method if request else "N/A",
        request.get_full_path() if request else "N/A",
        str(exc),
        exc_info=True  # includes full traceback
    )

    return Response(
        {"error": normalize_error("An unexpected error occurred. Please contact support.")},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
