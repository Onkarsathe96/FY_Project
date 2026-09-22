import uvicorn
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from app.config import TEMPLATES_DIR
from app.routers import ingestion_routes, analytics_routes

app = FastAPI(title="CloudOptima - Manual Ingestion FinOps")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(ingestion_routes.router)
app.include_router(analytics_routes.router)

@app.get("/")
def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)