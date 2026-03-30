from fastapi import APIRouter, Query

from app.utils.bd_address import BD_DIVISIONS

router = APIRouter(prefix="/api/bd-address", tags=["BD Address"])


@router.get("/divisions")
async def get_divisions():
    return sorted(BD_DIVISIONS.keys())


@router.get("/districts")
async def get_districts(division: str = Query(...)):
    districts = BD_DIVISIONS.get(division, {})
    return sorted(districts.keys())


@router.get("/upazilas")
async def get_upazilas(division: str = Query(...), district: str = Query(...)):
    upazilas = BD_DIVISIONS.get(division, {}).get(district, [])
    return sorted(upazilas)
