import json
import logging

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
from django.conf import settings
from django.apps import apps

from djaq.query import DjangoQuery as DQ
from djaq import app_utils

logger = logging.getLogger(__name__)


def queries(query_list):
    if not query_list:
        return []
    responses = []
    for data in query_list:
        query_string = data.get("q")
        offset = int(data.get("offset", 0))
        limit = int(data.get("limit", 0))
        context = data.get("context", {})
        responses.append(
            list(DQ(query_string).context(context).limit(limit).offset(offset).dicts())
        )
    return responses


def creates(creates_list):
    if not creates_list:
        return []
    responses = []
    for data in creates_list:
        model = app_utils.find_model_class(data.pop("_model"))
        instance = model.objects.create(**data)
        responses.append(instance.pk)
    return responses


def updates(updates_list):

    #  import ipdb; ipdb.set_trace()

    if not updates_list:
        return []
    responses = []
    for data in updates_list:
        model = app_utils.find_model_class(data.pop("_model"))
        cnt = model.objects.filter(pk=data.pop("_pk")).update(**data)
        responses.append(cnt)
    return responses


def deletes(deletes_list):
    if not deletes_list:
        return []
    responses = []
    for data in deletes_list:
        model = app_utils.find_model_class(data.pop("_model"))
        cnt = model.objects.filter(pk=data.pop("_pk")).delete()
        responses.append(cnt)
    return responses


@csrf_exempt
@login_required
def djaq_view(request):
    logger.debug(request.body)
    data = json.loads(request.body.decode("utf-8"))

    try:
        return JsonResponse(
            {
                "result": {
                    "queries": queries(data.get("queries")),
                    "creates": creates(data.get("creates")),
                    "updates": updates(data.get("updates")),
                    "deletes": deletes(data.get("deletes")),
                }
            }
        )
    except Exception as e:
        logger.exception(e)
        return HttpResponseServerError(e)


@csrf_exempt
@login_required
def djaq_schema_view(request):
    whitelist = {}
    try:
        return JsonResponse(app_utils.get_schema(whitelist=whitelist))
    except Exception as e:
        logger.exception(e)
        return HttpResponseServerError(e)
