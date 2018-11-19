from django.apps import apps



# Make list of models and fields


m._meta.db_table # name of db table

fields = m._meta.fields # fields tuple

f = fields[0]

f.name # field name



def find_model_class(name):
    list_of_apps = list(apps.get_app_configs())
    for a in list_of_apps:
        for model_name, model_class in a.models.items():
            if name == model_class.__name__:
                return model_class

def fieldclass_from_model(field_name, model):
    """Return a field class named field_name."""
    for f in model._meta.fields:
        if field_name == f.name:
            return f
        
def qualified_field(field_ref):
    """return string for field reference.

    like 'User.

    """

    model_name, field_name = field_ref.split('.')
    model_class = find_model_class(model_name)
    field_class = field_from_model(field_name, model_class)
    

    
