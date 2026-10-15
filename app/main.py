"""
Employee Management Dashboard - FastAPI backend.

- REST API under /api, dashboard served from "/".
- Uses MongoDB Atlas when MONGODB_URI is set and reachable.
- If MongoDB is not reachable, it falls back to a temporary in-memory store
  so the app still runs (data is lost on restart). /api/health shows which one is active.
"""
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
DB_NAME = os.getenv("MONGODB_DB", "hrone_db")
COLLECTION = "employees"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
Status = Literal["active", "on_leave", "inactive"]


# ---------- Schemas ----------
class EmployeeIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=120)
    department: str = Field(min_length=2, max_length=60)
    role: str = Field(min_length=2, max_length=60)
    status: Status = "active"

    @field_validator("name", "department", "role")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("must be at least 2 characters")
        return v

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    email: Optional[str] = Field(default=None, max_length=120)
    department: Optional[str] = Field(default=None, min_length=2, max_length=60)
    role: Optional[str] = Field(default=None, min_length=2, max_length=60)
    status: Optional[Status] = None

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v


# ---------- Storage layers ----------
class DuplicateEmail(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _matches(doc: dict, q: str, department: Optional[str], status: Optional[str]) -> bool:
    if department and doc["department"].lower() != department.lower():
        return False
    if status and doc["status"] != status:
        return False
    if q:
        ql = q.lower()
        if not any(ql in doc[k].lower() for k in ("name", "email", "role")):
            return False
    return True


class MemoryStore:
    mode = "memory"

    def __init__(self) -> None:
        self.data: Dict[str, dict] = {}

    def find(self, q, department, status, skip, limit) -> Tuple[List[dict], int]:
        rows = [d for d in self.data.values() if _matches(d, q, department, status)]
        rows.sort(key=lambda d: d["created_at"], reverse=True)
        return rows[skip: skip + limit], len(rows)

    def get(self, emp_id: str) -> Optional[dict]:
        return self.data.get(emp_id)

    def insert(self, doc: dict) -> dict:
        if any(d["email"] == doc["email"] for d in self.data.values()):
            raise DuplicateEmail()
        doc["id"] = uuid.uuid4().hex
        self.data[doc["id"]] = doc
        return doc

    def update(self, emp_id: str, changes: dict) -> Optional[dict]:
        doc = self.data.get(emp_id)
        if not doc:
            return None
        if "email" in changes and any(
            d["email"] == changes["email"] and d["id"] != emp_id for d in self.data.values()
        ):
            raise DuplicateEmail()
        doc.update(changes)
        return doc

    def delete(self, emp_id: str) -> bool:
        return self.data.pop(emp_id, None) is not None

    def stats(self) -> dict:
        by_status: Dict[str, int] = {}
        by_dept: Dict[str, int] = {}
        for d in self.data.values():
            by_status[d["status"]] = by_status.get(d["status"], 0) + 1
            by_dept[d["department"]] = by_dept.get(d["department"], 0) + 1
        return {"total": len(self.data), "by_status": by_status, "by_department": by_dept}


class MongoStore:
    mode = "mongodb"

    def __init__(self, client: MongoClient) -> None:
        self.col = client[DB_NAME][COLLECTION]
        self.col.create_index([("email", ASCENDING)], unique=True)

    @staticmethod
    def _out(doc: Optional[dict]) -> Optional[dict]:
        if doc is None:
            return None
        doc = dict(doc)
        doc["id"] = str(doc.pop("_id"))
        return doc

    @staticmethod
    def _oid(emp_id: str) -> Optional[ObjectId]:
        try:
            return ObjectId(emp_id)
        except (InvalidId, TypeError):
            return None

    def find(self, q, department, status, skip, limit) -> Tuple[List[dict], int]:
        query: dict = {}
        if department:
            query["department"] = {"$regex": f"^{re.escape(department)}$", "$options": "i"}
        if status:
            query["status"] = status
        if q:
            rx = {"$regex": re.escape(q), "$options": "i"}
            query["$or"] = [{"name": rx}, {"email": rx}, {"role": rx}]
        total = self.col.count_documents(query)
        cur = self.col.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        return [self._out(d) for d in cur], total

    def get(self, emp_id: str) -> Optional[dict]:
        oid = self._oid(emp_id)
        return self._out(self.col.find_one({"_id": oid})) if oid else None

    def insert(self, doc: dict) -> dict:
        try:
            res = self.col.insert_one(dict(doc))
        except DuplicateKeyError:
            raise DuplicateEmail()
        doc["id"] = str(res.inserted_id)
        return doc

    def update(self, emp_id: str, changes: dict) -> Optional[dict]:
        oid = self._oid(emp_id)
        if not oid:
            return None
        try:
            res = self.col.find_one_and_update(
                {"_id": oid}, {"$set": changes}, return_document=True
            )
        except DuplicateKeyError:
            raise DuplicateEmail()
        return self._out(res)

    def delete(self, emp_id: str) -> bool:
        oid = self._oid(emp_id)
        return bool(oid) and self.col.delete_one({"_id": oid}).deleted_count == 1

    def stats(self) -> dict:
        by_status = {r["_id"]: r["n"] for r in self.col.aggregate(
            [{"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
        by_dept = {r["_id"]: r["n"] for r in self.col.aggregate(
            [{"$group": {"_id": "$department", "n": {"$sum": 1}}}])}
        return {"total": self.col.count_documents({}), "by_status": by_status,
                "by_department": by_dept}


def build_store():
    """Try MongoDB first; fall back to memory so the app always starts."""
    if not MONGODB_URI:
        print("[startup] MONGODB_URI not set -> using in-memory store")
        return MemoryStore(), "MONGODB_URI is not set"
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=4000)
        client.admin.command("ping")
        print("[startup] Connected to MongoDB")
        return MongoStore(client), None
    except PyMongoError as exc:
        print(f"[startup] MongoDB connection failed -> using in-memory store: {exc}")
        return MemoryStore(), "MongoDB connection failed"


store, db_warning = build_store()

# ---------- App ----------
app = FastAPI(title="Employee Dashboard API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _new_doc(data: EmployeeIn) -> dict:
    now = _now()
    return {**data.model_dump(), "created_at": now, "updated_at": now}


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "storage": store.mode, "warning": db_warning}


@app.get("/api/employees")
def list_employees(
    q: str = Query("", max_length=80),
    department: Optional[str] = None,
    status: Optional[Status] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    items, total = store.find(q.strip(), department, status, skip, limit)
    return {"items": items, "total": total}


@app.post("/api/employees", status_code=201)
def create_employee(payload: EmployeeIn):
    try:
        return store.insert(_new_doc(payload))
    except DuplicateEmail:
        raise HTTPException(409, "An employee with this email already exists")
    except PyMongoError:
        raise HTTPException(503, "Database error, please try again")


@app.get("/api/employees/{emp_id}")
def get_employee(emp_id: str):
    doc = store.get(emp_id)
    if not doc:
        raise HTTPException(404, "Employee not found")
    return doc


@app.put("/api/employees/{emp_id}")
def update_employee(emp_id: str, payload: EmployeeUpdate):
    changes = payload.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(400, "No fields to update")
    changes["updated_at"] = _now()
    try:
        doc = store.update(emp_id, changes)
    except DuplicateEmail:
        raise HTTPException(409, "An employee with this email already exists")
    except PyMongoError:
        raise HTTPException(503, "Database error, please try again")
    if not doc:
        raise HTTPException(404, "Employee not found")
    return doc


@app.delete("/api/employees/{emp_id}", status_code=204)
def delete_employee(emp_id: str):
    if not store.delete(emp_id):
        raise HTTPException(404, "Employee not found")


@app.get("/api/stats")
def get_stats():
    return store.stats()
