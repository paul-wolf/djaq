from django.apps import apps
from django.db import models, connections
from django.db.models.fields import NOT_PROVIDED

from .exceptions import ModelNotFoundException


def model_path(model):
    """Return the dot path of a model."""
    return f"{model.__module__}.{model._meta.object_name}"


def get_db_type(field, connection):
    """Return a string indicating what kind of database."""
    if isinstance(
        field, (models.PositiveSmallIntegerField, models.PositiveIntegerField)
    ):
        # integer CHECK ("points" >= 0)'
        return field.db_type(connection).split(" ", 1)[0]

    return field.db_type(connection)


def find_model_class(model_label, whitelist=None):
    """Return model class for name, like 'Book'.
    app_label is an app **label**
    The label is the same as app name if your apps.py doesn't
    provide a label.
    If name has dots, then everything before the last segment
    is an app specifier

    """
    #  import ipdb; ipdb.set_trace()
    if "." in model_label:
        class_name = model_label.split(".")[-1]
        model_label = ".".join(model_label.split(".")[:-1])
    else:
        class_name = model_label
        model_label = None

    list_of_apps = list(apps.get_app_configs())
    for a in list_of_apps:

        if whitelist and a.name not in whitelist:
            continue

        if model_label and not model_label == a.label:
            continue
        for model_name, model_class in a.models.items():
            if whitelist and a.label in whitelist:
                if whitelist[a.label] and model_class.__name__ not in whitelist[a.label]:
                    continue
            if class_name == model_class.__name__:
                return model_class

    raise ModelNotFoundException(f"Could not find model label: {model_label}")


def get_model_from_table(table_name):
    """Return Model class from underlying db table."""
    list_of_apps = list(apps.get_app_configs())
    for a in list_of_apps:
        for model_name, model_class in a.models.items():
            if model_class._meta.db_table == table_name:
                return model_class
    raise ModelNotFoundException(f"Could not find model for table: {table_name}")


def fieldclass_from_model(field_name, model):
    """Return a field class named field_name."""
    return model._meta.get_field(field_name)


def get_field_from_model(model, fieldname):
    """Return Field object for Model.field."""
    for f in model._meta.get_fields():
        if f.name == fieldname:
            return f


def model_field(model_name, field_name):
    """Return tuple of (model, field).

    like:
       model = 'User'
       field = 'name'

    """

    model_class = find_model_class(model_name)
    if not model_class:
        raise Exception(f"No model class with name: {model_name}")
    return model_class, model_class._meta.get_field(field_name)


def field_ref(ref):
    """Shortcut for field model.

    like 'User.name'

    """
    return model_field(*ref.split("."))


def get_field_details(f, connection):
    """Return dict of field properties, json serialisable."""
    d = {}
    
    d["name"] = f.name
    d["unique"] = f.unique
    d["primary_key"] = f.primary_key
    if f.max_length:
        d["max_length"] = f.max_length
    d["internal_type"] = f.get_internal_type()
    d["db_type"] = str(f.db_type(connection=connection))
    if not f.default == NOT_PROVIDED:
        d["default"] = str(f.default)
    if f.related_model:
        d["related_model"] = f.related_model._meta.label
        d["related_model_field"] = str(f.target_field)
    if f.help_text:
        d["help_text"] = f.help_text
    return d


def get_model_details(cls, connection):
    fields = {}
    data = {}
    for f in cls._meta.fields:
        fields[f.name] = get_field_details(f, connection)
    data["fields"] = fields
    data["verbose_name"] = cls._meta.verbose_name
    data["label"] = cls._meta.label
    data["pk"] = str(cls._meta.pk)
    data["object_name"] = cls._meta.object_name
    #  data["db_table"] = cls._meta.db_table
    return data


def get_model_classes(app_name=None, whitelist=None):
    """Return all model classes.

    whitelist is a dictionary with appnames and lists of models
    that we are allowed to return.

    """
    list_of_apps = list(apps.get_app_configs())
    models = {}

    for a in list_of_apps:
        if app_name and not a.name == app_name:
            continue
        if whitelist and a.name not in whitelist:
            continue
        for model_name, model_class in a.models.items():
            if whitelist and a.name in whitelist:
                if whitelist[a.name] and model_class.__name__ not in whitelist[a.name]:
                    continue
            models[f"{a.name}.{model_class.__name__}"] = model_class
    return models


def get_schema(connection=None, whitelist=None):
    """Return json that represents all whitelisted app models."""
    connection = connection if connection else connections["default"]
    #  import ipdb; ipdb.set_trace()
    classes = get_model_classes(whitelist=whitelist)
    model_data = {}

    for label, cls in classes.items():
        model_data[label] = get_model_details(cls, connection)
    return model_data


def get_whitelist(whitelist=None):
    """Return the list apps models."""

    list_of_apps = list(apps.get_app_configs())
    wl = {}

    for a in list_of_apps:
        if whitelist and a.name not in whitelist:
            continue
        for model_name, model_class in a.models.items():
            if whitelist and a.name in whitelist:
                if whitelist[a.name] and model_class.__name__ not in whitelist[a.name]:
                    continue
            if a.name not in wl:
                wl[a.name] = []
            wl[a.name].append(model_class.__name__)
    return wl


TYPE_MAP = {
    'AutoField': "int",
    'CharField': "str",
    'IntegerField': "int",
    'DecimalField': "Decimal",
    'FloatField': "int",
    'ForeignKey': "int",
    'DateField': "datetime.date",
    'DateTimeField': "datetime.datetime",
    'BooleanField': "bool",
    'TextField': "str",
    'PositiveSmallIntegerField': "int",
    'OneToOneField': "int",
}
def map_type(field):
    """
    """
    return TYPE_MAP[field.get_internal_type()]


def make_dataclass(model, defaults=False, base_class=None):
    if isinstance(model, str):
        model = find_model_class(model)
    print("@dataclass")
    print(f"class {model._meta.object_name}Entity:")
    for f in model._meta.fields:
        print(f"    {f.name}: {map_type(f)}")
    print("")

def dataclass_mapper(klass, result_dict):
    """Create an instance of dataclass klass with data from result_dict."""
    data = dict()
    klass_keys = klass.__annotations__.keys()
    for key in result_dict.keys():
        if key in klass_keys:
            data[key] = result_dict[key]
    return klass(**data)

        