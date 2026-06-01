from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import SessionLocal
    from app.bootstrap import run
    from app.reloader import DockerReloader

    db = SessionLocal()
    try:
        run(db, DockerReloader())
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="naive-singbox", lifespan=lifespan)
    from app.routers import auth, clients, settings as settings_router, subscription

    app.include_router(auth.router, prefix="/api")
    app.include_router(clients.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(subscription.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
