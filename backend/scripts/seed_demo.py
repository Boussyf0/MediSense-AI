"""Seed demo accounts + sample clinic data so the apps look real in a demo.

There is no public /register endpoint — accounts are created by admins. This script
creates one account per role, a set of pseudonymized patients, and a spread of
appointments for the demo doctor (past/upcoming, varied statuses + no-show scores).

Idempotent: every row uses a deterministic UUID and is skipped if it already exists,
so the script is safe to re-run.

Run on Fly:   fly ssh console -a medisense-ai -C "python scripts/seed_demo.py"
Run locally:  python scripts/seed_demo.py   (with DB env pointing at the target)
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole

# Same password for every demo account — fine for a demo, never for production.
DEMO_PASSWORD = "Demo1234!"

_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "medisense-demo")


def _id(label: str) -> uuid.UUID:
    """Deterministic UUID for a label so re-runs don't create duplicates."""
    return uuid.uuid5(_NS, label)


# email,                    role,               first,     last,        specialty
DEMO_USERS = [
    ("admin@medisense.ai",     UserRole.ADMIN,     "Admin",   "MediSense", None),
    ("doctor@medisense.ai",    UserRole.DOCTOR,    "Yasmine", "El Amrani", "Cardiologie"),
    ("secretary@medisense.ai", UserRole.SECRETARY, "Sara",    "Bennani",   None),
    ("patient1@medisense.ai",  UserRole.PATIENT,   "Karim",   "Idrissi",   None),
    ("patient2@medisense.ai",  UserRole.PATIENT,   "Fatima",  "Zahra",     None),
]

# Standalone pseudonymized patients (no login) to fill out the doctor's roster.
# label, birth_year, sex, city_code, chronic_conditions
DEMO_PATIENTS = [
    ("patient:karim",  1979, "M", "CASA", ["hypertension"]),          # = patient1 login
    ("patient:fatima", 1990, "F", "RABA", []),                        # = patient2 login
    ("patient:omar",   1965, "M", "CASA", ["diabetes_t2", "hypertension"]),
    ("patient:salma",  1998, "F", "MARR", ["asthma"]),
    ("patient:youssef",1952, "M", "FES",  ["copd", "hypertension"]),
    ("patient:nadia",  1987, "F", "TANG", []),
]

# Appointments for the demo doctor: (patient_label, day_offset, status, noshow_prob)
DEMO_APPTS = [
    ("patient:karim",   -7, "COMPLETED", 0.12),
    ("patient:omar",    -3, "NO_SHOW",   0.71),
    ("patient:salma",   -1, "COMPLETED", 0.20),
    ("patient:fatima",   0, "CONFIRMED", 0.15),
    ("patient:youssef",  1, "CONFIRMED", 0.64),
    ("patient:nadia",    2, "PENDING",   0.33),
    ("patient:karim",    5, "PENDING",   0.18),
    ("patient:omar",     9, "CONFIRMED", 0.69),
]


def main() -> None:
    engine = create_engine(get_settings().DATABASE_URL_SYNC)
    now = datetime.now(timezone.utc)
    created = {"users": 0, "patients": 0, "appointments": 0}

    # patient login accounts reuse their user_uuid as patient_uuid (matches the
    # login self-heal), so map their labels to the deterministic user id.
    login_patient_uuid = {
        "patient:karim": _id("user:patient1@medisense.ai"),
        "patient:fatima": _id("user:patient2@medisense.ai"),
    }

    def patient_uuid(label: str) -> uuid.UUID:
        return login_patient_uuid.get(label, _id(label))

    with Session(engine) as db:
        # 1) Users
        for email, role, first, last, specialty in DEMO_USERS:
            uid = _id(f"user:{email}")
            if db.get(User, uid) is None:
                db.add(User(
                    user_uuid=uid,
                    email=email,
                    hashed_password=hash_password(DEMO_PASSWORD),
                    role=role,
                    first_name=first,
                    last_name=last,
                    specialty=specialty,
                ))
                created["users"] += 1

        # 2) Patients
        for label, birth_year, sex, city, conditions in DEMO_PATIENTS:
            pid = patient_uuid(label)
            if db.get(Patient, pid) is None:
                db.add(Patient(
                    patient_uuid=pid,
                    consent_iot=True,
                    consent_nlp=True,
                    consent_sharing=False,
                    birth_year=birth_year,
                    sex=sex,
                    city_code=city,
                    chronic_conditions=conditions or None,
                ))
                created["patients"] += 1

        # 3) Appointments for the demo doctor
        doctor_uuid = _id("user:doctor@medisense.ai")
        for i, (plabel, day_offset, statusv, noshow) in enumerate(DEMO_APPTS):
            aid = _id(f"appt:{i}:{plabel}")
            if db.get(Appointment, aid) is None:
                db.add(Appointment(
                    appointment_uuid=aid,
                    patient_uuid=patient_uuid(plabel),
                    doctor_uuid=doctor_uuid,
                    scheduled_at=(now + timedelta(days=day_offset)).replace(
                        hour=9 + (i % 7), minute=0, second=0, microsecond=0
                    ),
                    duration_minutes=20,
                    status=statusv,
                    noshow_probability=noshow,
                    noshow_model_ver="demo-1",
                ))
                created["appointments"] += 1

        db.commit()

    print(
        f"✓ seeded {created['users']} users, {created['patients']} patients, "
        f"{created['appointments']} appointments"
    )
    print(f"  login password for all accounts: {DEMO_PASSWORD}")
    for email, role, *_ in DEMO_USERS:
        print(f"  - {email}  ({role.value})")


if __name__ == "__main__":
    main()
