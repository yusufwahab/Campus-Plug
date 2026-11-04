"""Common Nigerian banks and their Paystack codes. Confirm against Paystack's /bank endpoint before going live."""

BANKS: dict[str, str] = {
    "Access Bank": "044",
    "Ecobank": "050",
    "FCMB": "214",
    "Fidelity Bank": "070",
    "First Bank": "011",
    "GTBank": "058",
    "Kuda": "50211",
    "Moniepoint": "50515",
    "OPay": "999992",
    "PalmPay": "999991",
    "Polaris Bank": "076",
    "Stanbic IBTC": "221",
    "Sterling Bank": "232",
    "UBA": "033",
    "Union Bank": "032",
    "Wema Bank": "035",
    "Zenith Bank": "057",
}


def bank_code(name: str) -> str | None:
    return BANKS.get(name)
