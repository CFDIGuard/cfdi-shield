"""Bank Shield v0.1 internal module component.

Current implementation remains in legacy shared app structure until modular
migration is safe.
"""

from pydantic import BaseModel


class BankReconciliationFilters(BaseModel):
    estado: str | None = None
    origen: str | None = None
    busqueda: str | None = None

    def cleaned(self) -> dict[str, str]:
        return {
            key: str(value).strip()
            for key, value in self.model_dump().items()
            if value not in (None, "") and str(value).strip()
        }
