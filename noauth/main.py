"""NoAuth."""

import logging
import logging.config

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from noauth.dependencies import setup

from noauth import oidc
from noauth import manual


LOG_LEVEL = logging.DEBUG
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "noauth": {
                "handlers": ["default"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
            "uvicorn": {
                "handlers": ["default"],
                "level": LOG_LEVEL,
                "propagate": True,
            },
        },
    }
)

app = FastAPI(lifespan=setup)

app.include_router(oidc.router)
app.include_router(manual.router)
app.mount("/", StaticFiles(directory="static"), name="static")
