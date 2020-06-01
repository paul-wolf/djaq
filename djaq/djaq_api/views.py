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


"""
settings:

DJAQ_WHITELIST
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


def is_allowed(op):
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
    return []


def queries(query_list, whitelist=None, validator=None):
    if not query_list:
        return []
    responses = []
    for data in query_list:
        query_string = data.get("q")
        offset = int(data.get("offset", 0))
        limit = int(data.get("limit", 0))
        context = data.get("context", {})
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
    if not is_allowed("creates"):
        return HttpResponse("Djaq unauthorized", status=401)
    if not creates_list:
        return []
    responses = []
    for data in creates_list:
        model = app_utils.find_model_class(data.pop("_model"), whitelist=whitelist)
        instance = model.objects.create(**data)
        responses.append(instance.pk)
    return responses


def updates(updates_list, whitelist=None):
    if not is_allowed("updates"):
        return HttpResponse("Djaq unauthorized", status=401)
    if not updates_list:
        return []
    responses = []
    for data in updates_list:
        model = app_utils.find_model_class(data.pop("_model"), whitelist=whitelist)
        cnt = model.objects.filter(pk=data.pop("_pk")).update(**data)
        responses.append(cnt)
    return responses


def deletes(deletes_list, whitelist=None):
    if not is_allowed("deletes"):
        return HttpResponse("Djaq unauthorized", status=401)
    if not deletes_list:
        return []
    responses = []
    for data in deletes_list:
        model = app_utils.find_model_class(data.pop("_model"), whitelist=whitelist)
        cnt = model.objects.filter(pk=data.pop("_pk")).delete()
        responses.append(cnt)
    return responses


@csrf_exempt
@login_required
def djaq_request_view(request):
    """Main view for query and update requests."""
    print(request.body)
    data = json.loads(request.body.decode("utf-8"))
    logger.debug(data)

    if not is_user_allowed(request.user):
        return HttpResponse("Djaq unauthorized", status=401)

    whitelist = get_whitelist()

    validator = get_validator()

    # import pudb; pudb.set_trace()
    # import ipdb; ipdb.set_trace()
    
    # add request to context
    q = data.get("queries")
    ctx = q[0].get("context")
    if not ctx:
        ctx = dict()
    # ctx["request"] = request
    # q["context"] = ctx

    try:
        return JsonResponse(
            {
                "result": {
                    "queries": queries(q, whitelist=whitelist, validator=validator),
                    "creates": creates(data.get("creates"), whitelist=whitelist),
                    "updates": updates(data.get("updates"), whitelist=whitelist),
                    "deletes": deletes(data.get("deletes"), whitelist=whitelist),
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
    try:
        return JsonResponse(app_utils.get_schema(whitelist=whitelist))
    except Exception as e:
        logger.exception(e)
        return HttpResponseServerError(e)
