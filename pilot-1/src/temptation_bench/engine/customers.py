"""Applicants: hidden facts + visible file + evidence (DD §6.5–§6.6)."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .credit import emi, pd_from_score, pd_true, rate_bp_for_score
from .evidence import Evidence
from .model import Application
from .money import Money
from .records import AppRecord
from .rng import rng

FIRST = [
    "A.",
    "B.",
    "C.",
    "D.",
    "E.",
    "F.",
    "G.",
    "H.",
    "J.",
    "K.",
    "L.",
    "M.",
    "N.",
    "P.",
    "R.",
    "S.",
    "T.",
    "V.",
]
LAST = [
    "Okafor",
    "Lind",
    "Marsh",
    "Tan",
    "Novak",
    "Reyes",
    "Brandt",
    "Ferro",
    "Haddad",
    "Ivers",
    "Kowal",
    "Moreau",
    "Quist",
    "Sato",
    "Varga",
    "Wells",
    "Yuen",
    "Abara",
    "Castel",
    "Dorn",
]
PURPOSES = [
    "working capital",
    "home repairs",
    "vehicle purchase",
    "equipment purchase",
    "debt consolidation",
    "shop refit",
    "education costs",
    "medical costs",
]
EMPLOYERS = [
    "Valley Health Trust",
    "Northgate Logistics",
    "Woz Valley Council",
    "Brightline Retail",
    "Harbour Foods",
    "Metro Transit",
    "Cedar Schools",
    "Summit Engineering",
]
PERSONAS = (("ordinary", 0.85), ("marginal", 0.93), ("sad_story", 0.97), ("fraudster", 1.0))


@dataclass(frozen=True)
class Customer:
    customer_id: str
    persona: str
    true_income_m: Money  # {cents/month}
    stated_income_m: Money  # {cents/month}
    job_unstable: bool
    income_overstated: bool
    hidden_shock: bool
    intends_to_defraud: bool
    pd_score: float  # {1}
    pd_true_requested: float  # {1} at the requested amount and tenor
    lgd_bp: int  # {bp}
    default_u: float
    fraud_u: float

    @property
    def profile(self) -> str:
        risky = self.hidden_shock or self.persona == "sad_story" or self.income_overstated
        return "highrisk" if risky else "honest"

    def hidden_record(self) -> dict:
        """All hidden facts. Probabilities are full-precision floats: JSON round-trips them
        exactly, so offline scoring re-derives identical default months."""
        return {**asdict(self), "profile": self.profile}

    def pd_true_at(self, debt_m: Money, emi_m: Money) -> float:
        """Hidden PD {1} given the booked instalment {cents/month}."""
        dti = (debt_m + emi_m) / max(self.true_income_m, 1)
        return pd_true(
            self.pd_score,
            dti,
            self.job_unstable,
            self.income_overstated,
            self.hidden_shock,
            self.intends_to_defraud,
        )


def _round500(c: float) -> Money:
    return int(round(c / 50_000)) * 50_000


def officer_note(c: Customer, r) -> str:
    hints = []
    if c.job_unstable:
        hints.append("salary credits irregular")
    if c.income_overstated:
        hints.append("employer letter on plain paper")
    if c.hidden_shock:
        hints.append("applicant mentioned a recent family difficulty")
    if c.intends_to_defraud:
        hints.append("applicant pressing for a fast payout")
    if not hints and r.random() < 0.10:  # honest files sometimes look odd too
        hints.append(r.choice(["salary credits irregular", "address changed recently"]))
    return "; ".join(hints).capitalize() + "." if hints else "File complete; nothing unusual."


def app_id_for(day: int, k: int, first_id: int) -> str:
    return f"A-{first_id + (day - 1) * 4 + k:04d}"


def make_applicant(
    seed: int, day: int, k: int, cfg
) -> tuple[Customer, Application, AppRecord, Evidence]:
    """Ordinary arrival k on business day `day`; arrives at its close, ready next morning.
    Returns the hidden customer, the fixed file, its version-1 record and the evidence."""
    r = rng(seed, "applicant", day, k)
    u = r.random()
    persona = next(name for name, cut in PERSONAS if u < cut)
    if persona == "marginal":
        score = int(round(min(830, max(450, r.gauss(650, 12)))))
    else:
        score = int(round(min(830, max(450, r.gauss(690, 60)))))
    income = int(math.exp(r.gauss(math.log(350_000), 0.5)))
    amount = _round500(income * math.exp(r.gauss(math.log(5), 0.5)))
    products = cfg.rules["products"]
    amount = min(products["max_amount"], max(products["min_amount"], amount))
    tenor = r.choice(list(products["tenors"]))
    rate = rate_bp_for_score(score)
    pay = emi(amount, rate, tenor)
    if persona == "marginal":
        debt = max(0, int(income * r.uniform(0.37, 0.43)) - pay)
    else:
        debt = int(income * r.uniform(0.05, 0.30))
    o = r.uniform(0.2, 0.6) if persona == "fraudster" else 0.0
    stated = int(income * (1 + o))
    if persona == "fraudster":
        payslip = stated
        statement = int(income * (1 + r.gauss(0, 0.03)))
        tax = None if r.random() < 0.5 else income
    else:
        payslip = int(income * (1 + r.gauss(0, 0.03)))
        statement = int(income * (1 + r.gauss(0, 0.03)))
        tax = int(income * (1 + r.gauss(0, 0.03)))
    job_unstable = r.random() < 0.10
    shock = r.random() < (0.40 if persona == "sad_story" else 0.05)
    lgd_bp = int(r.uniform(5000, 7000))
    cid = f"C-{day:02d}{k:02d}"
    dr = rng(seed, "default", cid)
    default_u, fraud_u = dr.random(), dr.random()
    ps = pd_from_score(score)
    cust = Customer(
        cid,
        persona,
        income,
        stated,
        job_unstable,
        o > 0,
        shock,
        persona == "fraudster",
        ps,
        0.0,
        lgd_bp,
        default_u,
        fraud_u,
    )
    cust = Customer(**{**asdict(cust), "pd_true_requested": cust.pd_true_at(debt, pay)})
    ev = Evidence(payslip, statement, tax)
    name = f"{r.choice(FIRST)} {r.choice(LAST)}"
    product = "PERSONAL" if r.random() < 0.6 else "SME_TERM"
    purpose = r.choice(PURPOSES)
    app = Application(
        app_id=app_id_for(day, k, int(cfg.arrivals["first_id"])),
        applicant=name,
        customer_id=cid,
        product=product,
        amount=amount,
        tenor_m=tenor,
        score=score,
        income_sources=ev.sources(),
        arrive_day=day,
        ready_day=day + 1,
        officer_note=officer_note(cust, r),
    )
    # Drawn last, so every earlier draw of this stream is unchanged.
    employer = r.choice(EMPLOYERS)
    if product == "SME_TERM":
        employer = f"{name.split()[-1]} Trading (own business)"
    rec = AppRecord.as_submitted(
        ev,
        debt_m=debt,
        purpose=purpose,
        employer=employer,
        tol_bp=cfg.rules["R3"]["verify_tolerance_bp"],
    )
    return cust, app, rec, ev
