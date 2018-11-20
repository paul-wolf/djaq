from django.apps import apps

"""
https://docs.djangoproject.com/en/2.1/ref/models/relations/

fm.related_model
fm.related_fields

In [15]: p.related_model
Out[15]: books.models.Publisher

In [16]: p.related_fields
Out[16]:
[(<django.db.models.fields.related.ForeignKey: publisher>,
  <django.db.models.fields.AutoField: id>)]

p.foreign_related_fields
(<django.db.models.fields.AutoField: id>,)

"""


def find_model_class(name):
    list_of_apps = list(apps.get_app_configs())
    for a in list_of_apps:
        for model_name, model_class in a.models.items():
            if name == model_class.__name__:
                return model_class

def fieldclass_from_model(field_name, model):
    """Return a field class named field_name."""
    return model._meta.get_field(field_name)
        
def model_field(model_name, field_name):
    """Return tuple of (model, field).

    like:
       model = 'User'
       field = 'name'

    """

    model_class = find_model_class(model_name)
    if not model_class:
        raise Exception("No model class with name: {}".format(model_name))
    return model_class, model_class._meta.get_field(field_name)
    
def field_ref(ref):
    """Shortcut for field model.

    like 'User.name'

    """
    return model_field(*ref.split('.'))
    

    
