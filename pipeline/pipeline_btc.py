from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Protocol, Literal, Dict, Any, List, Optional
import sqlite3
import json
import time

Currency = Literal["USD", "EUR", "GBP"]

class PipelineError(Exception): ...
class ValidationError(PipelineError): ...
class AuthError(PipelineError): ...
class TransformError(PipelineError): ...
class StorageError(PipelineError): ...

@dataclass
class Transaction:
    user_id: str
    btc_amount: float
    base_currency: Currency
    btc_price_in_base: Optional[float] = None
    subtotal_base: Optional[float] = None
    commission_usd: float = 5.0
    commission_base: Optional[float] = None
    total_base: Optional[float] = None
    ts_epoch: int = int(time.time())

@dataclass
class User:
    user_id: str
    name: str
    active: bool = True

class RateProvider(Protocol):
    def get_btc_price(self, currency: Currency) -> float: ...
    def usd_to(self, currency: Currency) -> float: ...

class FixedRateProvider:
    """
    Proveedor simulado:
    - Precios BTC
    - FX USD -> {USD,EUR,GBP}
    """
    def __init__(self):
        self._btc = {
            "USD": 65000.0,
            "EUR": 61000.0,
            "GBP": 53000.0,
        }
        self._fx_usd = {
            "USD": 1.0,
            "EUR": 0.93,
            "GBP": 0.80,
        }

    def get_btc_price(self, currency: Currency) -> float:
        if currency not in self._btc:
            raise TransformError(f"Moneda no soportada para precio BTC: {currency}")
        return self._btc[currency]

    def usd_to(self, currency: Currency) -> float:
        if currency not in self._fx_usd:
            raise TransformError(f"Moneda no soportada para FX: {currency}")
        return self._fx_usd[currency]

class Filter(Protocol):
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]: ...

class ValidationFilter:
    """Verificar que la transacción tenga datos obligatorios y válidos."""
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tx: Transaction = context["transaction"]
        if not tx.user_id or not isinstance(tx.user_id, str):
            raise ValidationError("Falta user_id válido.")
        if not isinstance(tx.btc_amount, (int, float)) or tx.btc_amount <= 0:
            raise ValidationError("btc_amount debe ser numérico y > 0.")
        if tx.base_currency not in ("USD", "EUR", "GBP"):
            raise ValidationError("base_currency debe ser USD, EUR o GBP.")
        return context

class AuthFilter:
    """Autenticar al usuario contra una 'BD' simulada."""
    def __init__(self, users_index: Dict[str, User]):
        self.users = users_index

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tx: Transaction = context["transaction"]
        user = self.users.get(tx.user_id)
        if user is None:
            raise AuthError(f"Usuario {tx.user_id} no existe.")
        if not user.active:
            raise AuthError(f"Usuario {tx.user_id} está inactivo.")
        context["user"] = user
        return context

class TransformFilter:
    """Convertir el monto de BTC a la moneda base usando el proveedor de tasas."""
    def __init__(self, rates: RateProvider):
        self.rates = rates

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tx: Transaction = context["transaction"]
        price = self.rates.get_btc_price(tx.base_currency)
        tx.btc_price_in_base = price
        tx.subtotal_base = round(price * tx.btc_amount, 2)
        return context

class FeeFilter:
    """
    Calcular la comisión: fija en USD (p.ej. 5.00 USD) y la convierte a la moneda base.
    Suma la comisión al total.
    """
    def __init__(self, rates: RateProvider):
        self.rates = rates

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tx: Transaction = context["transaction"]
        if tx.subtotal_base is None:
            raise TransformError("Falta subtotal_base; ejecute TransformFilter antes.")
        fx = self.rates.usd_to(tx.base_currency)
        tx.commission_base = round(tx.commission_usd * fx, 2)
        tx.total_base = round(tx.subtotal_base + tx.commission_base, 2)
        return context

class StorageFilter:
    """Guardar la transacción en SQLite."""
    def __init__(self, db_path: str = "transactions.db"):
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    btc_amount REAL NOT NULL,
                    base_currency TEXT NOT NULL,
                    btc_price_in_base REAL,
                    subtotal_base REAL,
                    commission_usd REAL,
                    commission_base REAL,
                    total_base REAL,
                    ts_epoch INTEGER
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tx: Transaction = context["transaction"]
        required = [tx.subtotal_base, tx.total_base, tx.commission_base, tx.btc_price_in_base]
        if any(v is None for v in required):
            raise StorageError("Transacción incompleta; verifique filtros previos.")

        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO transactions(
                    user_id, btc_amount, base_currency,
                    btc_price_in_base, subtotal_base,
                    commission_usd, commission_base, total_base, ts_epoch
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    tx.user_id, tx.btc_amount, tx.base_currency,
                    tx.btc_price_in_base, tx.subtotal_base,
                    tx.commission_usd, tx.commission_base, tx.total_base, tx.ts_epoch
                )
            )
            conn.commit()
        except sqlite3.DatabaseError as e:
            raise StorageError(f"Error al guardar en SQLite: {e}")
        finally:
            conn.close()

        context["storage_result"] = "ok"
        return context

class Pipeline:
    def __init__(self, filters: List[Filter]):
        self.filters = filters

    def run(self, transaction: Transaction) -> Dict[str, Any]:
        context: Dict[str, Any] = {"transaction": transaction}
        for f in self.filters:
            context = f.process(context)
        return context

def load_mock_users() -> Dict[str, User]:
    # Podrías cargar esto de un JSON local; aquí lo dejamos en memoria por simplicidad
    raw = [
        {"user_id": "u001", "name": "Alice", "active": True},
        {"user_id": "u002", "name": "Bob", "active": True},
        {"user_id": "u003", "name": "Carol", "active": False},  # inactivo para probar AuthError
    ]
    return {r["user_id"]: User(**r) for r in raw}

def main():
    users = load_mock_users()
    rates = FixedRateProvider()

    pipeline = Pipeline(filters=[
        ValidationFilter(),
        AuthFilter(users_index=users),
        TransformFilter(rates=rates),
        FeeFilter(rates=rates),
        StorageFilter(db_path="transactions.db"),
    ])

    examples = [
        Transaction(user_id="u001", btc_amount=0.01, base_currency="USD"),
        Transaction(user_id="u002", btc_amount=0.05, base_currency="EUR"),
        Transaction(user_id="u001", btc_amount=0.003, base_currency="GBP"),
        # Transaction(user_id="u003", btc_amount=0.02, base_currency="USD"),  # usuario inactivo -> AuthError
        # Transaction(user_id="u999", btc_amount=0.02, base_currency="USD"),  # usuario inexistente -> AuthError
    ]

    results: List[Dict[str, Any]] = []
    for tx in examples:
        try:
            ctx = pipeline.run(tx)
            results.append({
                "ok": True,
                "transaction": asdict(tx),
                "user": asdict(ctx["user"]),
                "storage_result": ctx.get("storage_result")
            })
        except PipelineError as e:
            results.append({
                "ok": False,
                "error": type(e).__name__,
                "message": str(e),
                "transaction": asdict(tx),
            })

    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()