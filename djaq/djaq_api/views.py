import sys
import traceback
import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import (
    HttpResponse,
    JsonResponse,
    HttpResponseServerError,
)

from djaq import DjaqQuery as DQ
from djaq import app_utils
from djaq import Writer, transaction


logger = logging.getLogger(__name__)

#  import pdb

"""
settings:

DJAQ_WHITELIST or DJAQ_ALLOW_MODELS
DJAQ_UI_URL
DJAQ_API_URL
DJAQ_PERMS = {
staff: true
admin: true
groups: []
}

"""


def is_user_allowed(user):
    """Return True if there are no blocking permissions in settings.DJAQ_PERMISSIONS."""

    if hasattr(settings, "DJAQ_PERMISSIONS"):
        perms = settings.DJAQ_PERMISSIONS
        if perms.get("staff") and not user.is_staff:
            return False
        if perms.get("superuser") and not user.is_superuser:
            return False

    return True


def has_permission(op):
    """Return True if op is allowed else False."""
    if hasattr(settings, "DJAQ_PERMISSIONS"):
        return settings.DJAQ_PERMISSIONS.get(op)
    return False


def get_validator():
    """Return validator specified in settings."""
    if hasattr(settings, "DJAQ_VALIDATOR"):
        return settings.DJAQ_VALIDATOR
    return None


def get_whitelist():
    if hasattr(settings, "DJAQ_WHITELIST"):
        return settings.DJAQ_WHITELIST
    elif hasattr(settings, "DJAQ_ALLOW_MODELS"):
        return settings.DJAQ_ALLOW_MODELS
    return list()


def get_scope(user):
    """Return a caller-scoped Schema (the read surface) or None.

    Configure ``DJAQ_SCOPE = func(user) -> Schema`` in settings to give each
    caller a different view; resolution is then confined to that schema (entity
    and field level). When unset, queries fall back to the global whitelist.
    """
    scope_fn = getattr(settings, "DJAQ_SCOPE", None)
    return scope_fn(user) if callable(scope_fn) else None


def queries(request_data, whitelist=None, validator=None, provider=None):

    query_list = request_data.get("queries")
    if not query_list:
        return list()
    responses = list()
    for data in query_list:
        model_name = data.get("model")
        output = data.get("output")
        where = data.get("where")
        order_by = data.get("order_by")
        page = int(data.get("page", 0))
        page_size = int(data.get("page_size", 0))

        if provider is not None:
            dq = DQ(model_name, output, provider=provider)
        else:
            dq = DQ(model_name, output, whitelist=whitelist)

        responses.append(
            list(
                dq.where(where)
                .order_by(order_by)
                .offset(page * page_size)
                .limit(page_size)
                .dicts()
            )
        )
    return responses


def creates(creates_list, whitelist=None):
    if not has_permission("creates"):
        return Exception("Creates not allowed")
    if not creates_list:
        return list()
    writer = Writer(whitelist=whitelist)
    return [writer.create(d["model"], d["fields"]) for d in creates_list]


def updates(updates_list, whitelist=None):
    if not has_permission("updates"):
        raise Exception("Updates not allowed")
    if not updates_list:
        return []
    writer = Writer(whitelist=whitelist)
    # instance.save() per row -> honours signals/defaults, unlike bulk update()
    return [writer.update(d["model"], d["pk"], d["fields"]) for d in updates_list]


def deletes(deletes_list, whitelist=None):
    if not has_permission("deletes"):
        raise Exception("Deletes not allowed")
    if not deletes_list:
        return list()
    writer = Writer(whitelist=whitelist)
    return [writer.delete(d["model"], d["pk"]) for d in deletes_list]


def get_context_data(data) -> dict:
    """Look for 'context' item in 'queries' item."""
    if "queries" in data:
        if "context" in data["queries"]:
            if isinstance(data["queries"], list):
                return data["queries"][0]["context"]
            else:
                return data["queries"]["context"]
    return dict()


@csrf_exempt
@login_required
def djaq_request_view(request):
    """Main view for query and update requests."""

    request_data = json.loads(request.body.decode("utf-8"))

    # print("-"*60)
    # print(request_data)
    # print("^"*60)

    if not is_user_allowed(request.user):
        return HttpResponse("Djaq unauthorized", status=401)

    whitelist = get_whitelist()

    validator = get_validator()

    # q = data.get("queries", dict()) or dict()
    # ctx = get_context_data(data)

    scope = get_scope(request.user)

    try:
        # one atomic boundary: a failed create/update/delete rolls the batch back
        with transaction():
            queries_result = queries(
                request_data, whitelist=whitelist, validator=validator, provider=scope
            )
            creates_result = (
                creates(request_data.get("creates"), whitelist=whitelist)
                if has_permission("creates")
                else list()
            )

            updates_result = (
                updates(request_data.get("updates"), whitelist=whitelist)
                if has_permission("updates")
                else list()
            )

            deletes_result = (
                deletes(request_data.get("deletes"), whitelist=whitelist)
                if has_permission("deletes")
                else list()
            )

        return JsonResponse(
            {
                "result": {
                    "queries": queries_result,
                    "creates": creates_result,
                    "updates": updates_result,
                    "deletes": deletes_result,
                }
            }
        )
    except Exception as e:

        print("-" * 60)
        traceback.print_exc(file=sys.stdout)
        print("-" * 60)

        if e.__cause__ and e.__cause__.pgerror:
            err = e.__cause__.pgerror
            logger.exception(err)
            return HttpResponseServerError(err)
        else:
            return HttpResponseServerError(e)


@csrf_exempt
@login_required
def djaq_schema_view(request):
    whitelist = []
    if not is_user_allowed(request.user):
        return HttpResponse("Djaq unauthorized", status=401)
    if hasattr(settings, "DJAQ_WHITELIST"):
        whitelist = settings.DJAQ_WHITELIST
    elif hasattr(settings, "DJAQ_ALLOW_MODELS"):
        whitelist = settings.DJAQ_ALLOW_MODELS
    try:
        return JsonResponse(app_utils.get_schema(whitelist=whitelist))
    except Exception as e:
        logger.exception(e)
        return HttpResponseServerError(e)
