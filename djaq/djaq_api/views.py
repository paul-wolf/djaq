import json
import logging

from django.conf import settings
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
    HttpResponseServerError,
)
from django.shortcuts import render
from django.apps import apps

from djaq.query import DjangoQuery as DQ
from djaq import app_utils

logger = logging.getLogger(__name__)

#  import ipdb

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


def queries(query_list, whitelist=None, validator=None):

    if not query_list:
        return list()
    responses = list()
    for data in query_list:
        query_string = data.get("q")
        offset = int(data.get("offset", 0))
        limit = int(data.get("limit", 0))
        context = data.get("context", dict())
        responses.append(
            list(
                DQ(query_string, whitelist=whitelist)
                .context(context)
                .validator(validator)
                .limit(limit)
                .offset(offset)
                .dicts()
            )
        )
    return responses


def creates(creates_list, whitelist=None):
    if not has_permission("creates"):
        return Exception("Creates not allowed")
    if not creates_list:
        return list()
    responses = list()
    for data in creates_list:
        model = app_utils.find_model_class(data.pop("_model"), whitelist=whitelist)
        instance = model.objects.create(**data)
        responses.append(instance.pk)
    return responses


def updates(updates_list, whitelist=None):
    if not has_permission("updates"):
        raise Exception("Updates not allowed")
    if not updates_list:
        return []
    responses = []
    for data in updates_list:
        model = app_utils.find_model_class(data.pop("_model"), whitelist=whitelist)
        cnt = model.objects.filter(pk=data.pop("_pk")).update(**data)
        responses.append(cnt)
    return responses


def deletes(deletes_list, whitelist=None):
    if not has_permission("deletes"):
        raise Exception("Deletes not allowed")
    if not deletes_list:
        return list()
    responses = list()
    for data in deletes_list:
        model = app_utils.find_model_class(data.pop("_model"), whitelist=whitelist)
        cnt = model.objects.filter(pk=data.pop("_pk")).delete()
        responses.append(cnt)
    return responses


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

    data = json.loads(request.body.decode("utf-8"))
    logger.debug(data)

    if not is_user_allowed(request.user):
        return HttpResponse("Djaq unauthorized", status=401)

    whitelist = get_whitelist()

    validator = get_validator()

    q = data.get("queries", dict()) or dict()
    ctx = get_context_data(data)
    # ctx["request"] = request

    try:
        queries_result = queries(q, whitelist=whitelist, validator=validator)
        creates_result = (
            creates(data.get("creates"), whitelist=whitelist)
            if has_permission("creates")
            else list()
        )

        updates_result = (
            updates(data.get("updates"), whitelist=whitelist)
            if has_permission("updates")
            else list()
        )

        deletes_result = (
            deletes(data.get("deletes"), whitelist=whitelist)
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
