"""Classification framework — the single source of truth for the taxonomy.

The brief asks us to classify each mention into a **reputation driver** and a more
specific **sub-driver**. We hard-code that taxonomy here (3 drivers → 8 sub-drivers)
together with a one-line description and a concrete few-shot example for each, taken
from the spirit of the assignment guide.

Everything downstream imports from this module:
- `classify.py` renders `taxonomy_prompt_block()` into the LLM prompt so the model
  sees the exact labels + examples it must choose from.
- `classify.py` calls `is_valid_driver()` / `is_valid_sub_driver()` to reject any
  label the model invents (the Zod-style "safeParse" discipline — never trust raw
  model output).

Keeping the taxonomy in one place means adding/renaming a driver is a one-edit change
and the prompt, validation, and dashboard all stay in sync automatically.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubDriver:
    """A leaf label under a driver, with guidance the LLM sees as a few-shot anchor."""

    name: str
    description: str
    example: str


@dataclass(frozen=True)
class Driver:
    """A top-level reputation driver and its sub-drivers."""

    name: str
    description: str
    sub_drivers: tuple[SubDriver, ...]


# --- The taxonomy ----------------------------------------------------------
# Order is intentional: it's the order the LLM sees and (later) the dashboard
# renders. Names here are the canonical strings stored in every output row.
TAXONOMY: tuple[Driver, ...] = (
    Driver(
        name="Brand Perception",
        description="How the market, media and thought-leaders perceive the brand's "
        "expertise, strategy and visibility.",
        sub_drivers=(
            SubDriver(
                name="Thought Leadership",
                description="Expert commentary, market outlook, or research that "
                "positions the brand's leaders as authorities.",
                example="ICICI Prudential's CIO shares his market outlook and views "
                "on equity valuations in an interview.",
            ),
            SubDriver(
                name="Product Strategy",
                description="Launch, design or positioning of funds and offerings; "
                "strategic business direction.",
                example="ICICI Prudential Mutual Fund launches two new offerings under "
                "the iSIF segment.",
            ),
            SubDriver(
                name="Brand Visibility & Marketing",
                description="Advertising, sponsorships, campaigns, rankings and general "
                "presence that raise brand awareness.",
                example="ICICI Prudential AMC features among the top wealth creators in "
                "an annual industry ranking.",
            ),
        ),
    ),
    Driver(
        name="User Experience",
        description="The lived experience of customers using the brand's products, "
        "service and digital channels.",
        sub_drivers=(
            SubDriver(
                name="Product & Service Quality",
                description="Fund performance, returns, fees and the quality of the "
                "core financial product.",
                example="A SIP in ICICI Prudential Equity & Debt Fund is shown to have "
                "grown to ₹4 crore over 26 years.",
            ),
            SubDriver(
                name="Customer Support & Complaint Resolution",
                description="Service responsiveness, grievance handling, call-centre and "
                "relationship-manager interactions.",
                example="An investor describes delays in getting a redemption complaint "
                "resolved by the AMC's support team.",
            ),
            SubDriver(
                name="Digital & Omnichannel Experience",
                description="App, website, onboarding and self-service journeys across "
                "digital and physical channels.",
                example="Users review the ICICI Prudential mobile app's KYC and SIP "
                "set-up flow.",
            ),
        ),
    ),
    Driver(
        name="Responsible Business Practices",
        description="Governance, compliance, ethics and the brand's social and "
        "community contribution.",
        sub_drivers=(
            SubDriver(
                name="Regulatory Compliance & Ethical Governance",
                description="SEBI/regulatory actions, disclosures, audits, fines, and "
                "governance or ethics matters.",
                example="SEBI issues a circular on expense-ratio disclosure that ICICI "
                "Prudential and peers must comply with.",
            ),
            SubDriver(
                name="Social Impact & Community (CSR)",
                description="CSR initiatives, financial-literacy drives, sustainability "
                "and community programmes.",
                example="ICICI Prudential AMC runs a financial-literacy programme for "
                "first-time investors in rural districts.",
            ),
        ),
    ),
)


# --- Lookups (built once at import) ----------------------------------------
_DRIVER_BY_NAME: dict[str, Driver] = {d.name: d for d in TAXONOMY}
_SUB_DRIVERS_BY_DRIVER: dict[str, set[str]] = {
    d.name: {s.name for s in d.sub_drivers} for d in TAXONOMY
}

DRIVER_NAMES: tuple[str, ...] = tuple(_DRIVER_BY_NAME)


def is_valid_driver(driver: str) -> bool:
    """True if `driver` is exactly one of the taxonomy's top-level driver names."""
    return driver in _DRIVER_BY_NAME


def is_valid_sub_driver(driver: str, sub_driver: str) -> bool:
    """True if `sub_driver` is a child of `driver` (both must match exactly)."""
    return sub_driver in _SUB_DRIVERS_BY_DRIVER.get(driver, set())


def sub_driver_names(driver: str) -> tuple[str, ...]:
    """The ordered sub-driver names under a driver (empty tuple if unknown)."""
    parent = _DRIVER_BY_NAME.get(driver)
    return tuple(s.name for s in parent.sub_drivers) if parent else ()


def taxonomy_prompt_block() -> str:
    """Render the taxonomy as a compact, LLM-friendly block for the classifier prompt.

    Lists every driver, its sub-drivers, and a one-line example per sub-driver so the
    model has both the allowed labels and a concrete anchor for each.
    """
    lines: list[str] = []
    for driver in TAXONOMY:
        lines.append(f"DRIVER: {driver.name} — {driver.description}")
        for sub in driver.sub_drivers:
            lines.append(f"  - SUB-DRIVER: {sub.name} — {sub.description}")
            lines.append(f"      e.g. {sub.example}")
        lines.append("")  # blank line between drivers for readability
    return "\n".join(lines).rstrip()


if __name__ == "__main__":  # quick manual check: `python pipeline/framework.py`
    import sys

    # The taxonomy examples contain ₹ etc.; force UTF-8 so the demo prints on
    # Windows consoles (cp1252) without crashing.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(taxonomy_prompt_block())
    print()
    print("Drivers:", DRIVER_NAMES)
    print("Total sub-drivers:", sum(len(d.sub_drivers) for d in TAXONOMY))
