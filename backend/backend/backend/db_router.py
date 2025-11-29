class SecretRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'services' and 'secret' in model._meta.model_name:
            return 'secrets'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'services' and 'secret' in model._meta.model_name:
            return 'secrets'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        if (obj1._meta.app_label == 'services' and 'secret' in obj1._meta.model_name) or (obj2._meta.app_label == 'services' and 'secret' in obj2._meta.model_name):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'services' and model_name and 'secret' in model_name:
            return db == 'secrets'
        return db == 'default'