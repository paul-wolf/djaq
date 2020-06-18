import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = "e4!hgr%iyac!e$x+coxw&qepouq(9a0)iersmd)y=0q6-n3#uf"

DEBUG = False

ALLOWED_HOSTS = ['localhost', '127.0.0.1']


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "books.apps.BooksConfig",
    "django_extensions",
    "djaq.djaq_ui",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bookshop.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "bookshop.wsgi.application"

DATABASES = {
    "default": {"ENGINE": "django.db.backends.postgresql_psycopg2", "NAME": "bookshop"}
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True


STATIC_URL = "/static/"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {pathname} {filename} {funcName} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "main": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "log/main.log"),
            "formatter": "verbose",
        },
        "parser": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "log/parser.log"),
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {"handlers": ["main"], "level": "DEBUG", "propagate": True},
        "db": {"handlers": ["main"], "level": "DEBUG", "propagate": True},
        "djaq.query": {"handlers": ["parser"], "level": "DEBUG", "propagate": True},
    },
}

DJAQ_WHITELIST = {
    "django.contrib.auth": ["User"],
    "books": [
        "Profile",
        "Author",
        "Consortium",
        "Publisher",
        "Book_authors",
        "Book",
        "Store_books",
        "Store",
    ],
}
DJAQ_UI_URL = None
DJAQ_API_URL = None
DJAQ_VALIDATOR = None
DJAQ_PERMISSIONS = {
    "creates": True,
    "updates": True,
    "deletes": True,
    "staff": False,
    "superuser": False,
}
