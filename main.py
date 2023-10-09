import argparse
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.middleware.cors import CORSMiddleware

from src import PHASE, logger
from src.common.consts import SERVICE_TITLE
from src.routes import upload

response_404 = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>Not Found</title>
        </head>
        <body>
            <h2>Please check the URL</h2>
        </body>
        </html>
        """


def create_app():
    if PHASE == "dev":
        app = FastAPI(title=SERVICE_TITLE)
    else:
        app = FastAPI(title=SERVICE_TITLE, docs_url=None, redoc_url=None)

    # app.include_router(status.router, tags=["Status"], prefix="/status")

    # 미들웨어 정의
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(upload.router, tags=["Upload"], prefix="/api")

    @app.exception_handler(404)
    async def custom_404_handler(_, __):
        return HTMLResponse(response_404)

    return app


app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--reload", action="store_true", default=False)
    args = parser.parse_args()

    if PHASE == "dev":
        logger.setLevel(logging.DEBUG)

        uvicorn.run(
            "main:app",
            host=args.ip,
            port=args.port,
            reload=args.reload,
            reload_dirs=["src"],
            log_config="log_config.yml",
        )

    else:
        uvicorn.run(
            "main:app",
            host=args.ip,
            port=args.port,
            workers=args.workers,
            log_config="log_config.yml",
        )
