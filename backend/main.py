from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.transactions import router as transactions_router
from backend.api.users import router as users_router

app = FastAPI(title="FIRE Finance Cockpit API")

# The MVP frontend is opened as a static file:// page (or a dev server on a
# different port) and calls this API cross-origin, so CORS must stay wide open.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions_router)
app.include_router(users_router)
