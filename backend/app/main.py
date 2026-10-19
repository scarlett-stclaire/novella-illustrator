from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import storage
from .routes import router

app = FastAPI(title="Novella Illustrator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


storage.init_storage()

app.include_router(router)
app.mount("/api/images", StaticFiles(directory=str(storage.IMAGES_DIR)), name="images")
app.mount("/api/exports", StaticFiles(directory=str(storage.EXPORTS_DIR)), name="exports")
