from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.accounts'
    label = 'accounts'

    def ready(self):
        import app.accounts.signals  # noqa: F401
