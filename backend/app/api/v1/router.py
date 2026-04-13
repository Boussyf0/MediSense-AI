"""
API v1 router — aggregates all endpoint routers.

Adding a new endpoint module:
  1. Create backend/app/api/v1/endpoints/my_feature.py
  2. Import its router here and add api_router.include_router(...)
"""
from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, patients, admin, chat

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(patients.router)   # Sprint 2: US-06, US-07, US-08
api_router.include_router(admin.router)      # Sprint 2: US-46 + Sprint 3: US-12 rerank-eval
api_router.include_router(chat.router)       # Sprint 3: US-09, US-10, US-11

# Sprint 4+: these will be added as they are built
# api_router.include_router(appointments.router)
# api_router.include_router(dpa.router)
