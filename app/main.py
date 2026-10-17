from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from app.pages import router as pages_router

app = FastAPI()
app.include_router(pages_router)


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"
