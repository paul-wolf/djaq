import sys
import traceback
import json
import logging

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

import psycopg2
import sqlparse

from djaq.query import DjangoQuery as DQ
from djaq.app_utils import get_schema, get_model_classes

logger = logging.getLogger(__name__)

#  @login_required
@csrf_exempt
def query_view(request):

    if request.method == "POST":
        print(request.POST)
        q = request.POST.get("query")
        limit = request.POST.get("limit", 10)
        offset = request.POST.get("offset", 0)
        sql = request.POST.get("sql", False) == "true"
        try:
            if sql:
                s = DQ(q).offset(offset).limit(limit).parse()
                s = sqlparse.format(s, reindent=True, keyword_case="upper")
                r = {"result": s}
            else:
                try:
                    r = {"result": list(DQ(q).offset(offset).limit(limit).dicts())}
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

    data = {}
    return render(request, "query.html", data)
