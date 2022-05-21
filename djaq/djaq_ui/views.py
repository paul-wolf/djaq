import sys
import traceback
import json
import logging

from django.apps import apps
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
    HttpResponseServerError,
)
from django.conf import settings
from django.db.utils import ProgrammingError
from django.db import models, connections

import psycopg2
import sqlparse

from djaq import DjaqQuery as DQ
from djaq.app_utils import (
    get_schema,
    get_model_classes,
    find_model_class,
    get_model_details,
    get_whitelist,
)
import ipdb

logger = logging.getLogger(__name__)


def wl():
    whitelist = dict()
    if hasattr(settings, "DJAQ_WHITELIST"):
        whitelist = settings.DJAQ_WHITELIST
    return whitelist


def get_params(data):
    model = data.get("model")
    output = data.get("output")
    where = data.get("where")
    order_by = data.get("order_by")
    return model, output, where, order_by


@login_required
@csrf_exempt
def query_view(request):

    if request.method == "POST":
        ipdb.set_trace()

        model, output, where, order_by = get_params(request.POST.get("queries")[0])
        limit = request.POST.get("limit", 10)
        offset = request.POST.get("offset", 0)
        sql = request.POST.get("sql", False) == "true"
        try:
            if sql:
                s = (
                    DQ(model, output, whitelist=wl())
                    .where(where)
                    .order_by(order_by)
                    .offset(offset)
                    .limit(limit)
                    .sql()
                )
                s = sqlparse.format(s, reindent=True, keyword_case="upper")
                r = {"result": s}
            else:
                try:
                    r = {
                        "result": list(
                            DQ(model, output, whitelist=wl())
                            .where(where)
                            .order_by(order_by)
                            .offset(offset)
                            .limit(limit)
                            .dicts()
                        )
                    }
                except Exception as e:
                    if e.__cause__ and e.__cause__.pgerror:
                        err = e.__cause__.pgerror
                        raise Exception(err)
                    else:
                        raise e
            return JsonResponse(r)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return HttpResponseServerError(e)

    list_of_apps = [a.name for a in apps.get_app_configs()]
    list_of_apps = filter(lambda a: a in list(wl().keys()), list_of_apps)
    data = {"apps": list_of_apps}
    return render(request, "query.html", data)


@login_required
@csrf_exempt
def sql_view(request):
    # ipdb.set_trace()
    print(request.body)
    request_data = json.loads(request.body.decode("utf-8"))
    print(request_data)
    model, output, where, order_by = get_params(request_data.get("queries")[0])
    try:
        s = DQ(model, output).where(where).order_by(order_by).sql()
        s = sqlparse.format(s, reindent=True, keyword_case="upper")
        r = {"result": s}
        return JsonResponse(r)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return HttpResponseServerError(e)


@login_required
@csrf_exempt
def get_models(request, appname):
    classes = get_model_classes(app_name=appname, whitelist=wl())
    model_names = []
    for label, cls in classes.items():
        model_names.append(label)
    return JsonResponse({"models": model_names})


@login_required
@csrf_exempt
def get_fields(request, modelname):
    model = find_model_class(modelname, whitelist=wl())
    d = get_model_details(model, connections["default"])
    return JsonResponse(d)


@login_required
@csrf_exempt
def get_whitelist_view(request):
    return JsonResponse(get_whitelist(whitelist=wl()))


@login_required
@csrf_exempt
def schema_view(request):
    return JsonResponse(get_schema(whitelist=wl()))
