from dataclasses import dataclass, field
from typing import Optional


CARD_BRANDS = {
    "visa": {
        "name": "VISA",
        "prefixes": ["4"],
        "lengths": [13, 16, 19],
        "cvv_length": 3,
        "colors": ("#1a1f71", "#2557d6"),
    },
    "mastercard": {
        "name": "Mastercard",
        "prefixes": ["51", "52", "53", "54", "55"] + [str(i) for i in range(2221, 2721)],
        "lengths": [16],
        "cvv_length": 3,
        "colors": ("#eb001b", "#f79e1b"),
    },
    "amex": {
        "name": "American Express",
        "prefixes": ["34", "37"],
        "lengths": [15],
        "cvv_length": 4,
        "colors": ("#006fcf", "#00a4e4"),
    },
    "jcb": {
        "name": "JCB",
        "prefixes": ["3528", "3529"] + [str(i) for i in range(3530, 3590)],
        "lengths": [16, 17, 18, 19],
        "cvv_length": 3,
        "colors": ("#0e4c96", "#c41f3e"),
    },
    "unionpay": {
        "name": "UnionPay",
        "prefixes": ["62", "81"],
        "lengths": [16, 17, 18, 19],
        "cvv_length": 3,
        "colors": ("#e21836", "#00447c"),
    },
    "discover": {
        "name": "Discover",
        "prefixes": ["6011", "644", "645", "646", "647", "648", "649", "65"],
        "lengths": [16, 17, 18, 19],
        "cvv_length": 3,
        "colors": ("#ff6600", "#d4a017"),
    },
}


def detect_brand(card_number: str) -> str:
    num = card_number.replace(" ", "").replace("-", "")
    for brand_id, info in CARD_BRANDS.items():
        for prefix in info["prefixes"]:
            if num.startswith(prefix) and len(num) in info["lengths"]:
                return brand_id
    return "unknown"


def luhn_check(card_number: str) -> bool:
    digits = [int(d) for d in card_number if d.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


@dataclass
class CardInfo:
    number: str
    expiry: str  # MM/YY
    cvv: str
    brand: str = field(default="unknown")

    def __post_init__(self):
        self.number = self.number.replace(" ", "").replace("-", "")
        if self.brand == "unknown":
            self.brand = detect_brand(self.number)

    @property
    def formatted_number(self) -> str:
        n = self.number
        if self.brand == "amex" and len(n) == 15:
            return f"{n[:4]} {n[4:10]} {n[10:]}"
        groups = [n[i:i+4] for i in range(0, len(n), 4)]
        return " ".join(groups)

    @property
    def masked_number(self) -> str:
        n = self.number
        if len(n) <= 8:
            return n
        return n[:4] + "*" * (len(n) - 8) + n[-4:]

    @property
    def brand_name(self) -> str:
        info = CARD_BRANDS.get(self.brand)
        return info["name"] if info else "Card"

    @property
    def brand_colors(self) -> tuple:
        info = CARD_BRANDS.get(self.brand)
        if info:
            return (info["colors"][0], info["colors"][1])
        return ("#6b5ce7", "#a855f7")

    @property
    def is_complete(self) -> bool:
        return bool(self.expiry) and bool(self.cvv)

    @property
    def is_valid(self) -> bool:
        return luhn_check(self.number) and len(self.expiry) >= 4 and len(self.cvv) >= 3

    def to_dict(self) -> dict:
        return {"cn": self.number, "exp": self.expiry, "cvv": self.cvv}
