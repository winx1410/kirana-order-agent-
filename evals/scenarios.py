"""Phase F evaluation cases.

Customer wording is the assignment text or a realistic follow-up.
The `nlu` field is a mocked Gemini structured response. These cases do not
call the Gemini API.
"""

CASES = [
    {
        "id": "official-1-rice-clarification",
        "title": "Sugar resolves; rice stays ambiguous until the customer chooses",
        "customer_id": "C002",
        "source": "Section 6, scenario 1, plus the follow-up selection",
        "turns": [
            {
                "message": "bhaiya 2 kg sugar, 5 kg rice send kar do",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "sugar", "quantity": 2, "unit": "kg", "action": "add"},
                        {"description": "rice", "quantity": 5, "unit": "kg", "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [("SKU-001", 2)],
                    "status": "clarifying",
                    "clarification_skus": ["SKU-002", "SKU-003", "SKU-004"],
                    "substitutions": [],
                    "order_status": None,
                    "stocks": {"SKU-001": 120, "SKU-002": 150},
                },
            },
            {
                "message": "Sona Masoori",
                "nlu": {
                    "intent": "clarification",
                    "mentions": [],
                    "clarification_text": "Sona Masoori",
                },
                "expect": {
                    "cart": [("SKU-001", 2), ("SKU-002", 5)],
                    "status": "awaiting_customer_confirmation",
                    "total": 402,
                    "clarification": False,
                    "approval_required": False,
                    "stocks": {"SKU-001": 120, "SKU-002": 150},
                },
            },
        ],
    },
    {
        "id": "official-2-usual-order",
        "title": "Usual order is shown with a bill and is not placed yet",
        "customer_id": "C004",
        "source": "Section 6, scenario 2",
        "turns": [
            {
                "message": "usual order bhejo",
                "nlu": {"intent": "usual_order", "mentions": []},
                "expect": {
                    "cart": [
                        ("SKU-001", 2),
                        ("SKU-024", 1),
                        ("SKU-017", 2),
                        ("SKU-028", 1),
                        ("SKU-027", 2),
                    ],
                    "status": "awaiting_customer_confirmation",
                    "total": 335,
                    "clarification": False,
                    "approval_required": False,
                    "order_status": None,
                    "stocks": {"SKU-001": 120, "SKU-017": 200, "SKU-027": 40},
                },
            }
        ],
    },
    {
        "id": "official-3-clean-confirm",
        "title": "Fortune oil and Parle-G bill at Rs.185, then explicit confirm",
        "customer_id": "C006",
        "source": "Section 6, scenario 3",
        "turns": [
            {
                "message": "1 litre Fortune oil and 5 Parle-G",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
                        {"description": "Parle-G", "quantity": 5, "unit": "pack", "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [("SKU-014", 1), ("SKU-017", 5)],
                    "status": "awaiting_customer_confirmation",
                    "total": 185,
                    "clarification": False,
                    "approval_required": False,
                    "order_status": None,
                    "stocks": {"SKU-014": 60, "SKU-017": 200},
                },
            },
            {
                "message": "haan, confirm",
                "nlu": {"intent": "confirm", "mentions": []},
                "expect": {
                    "cart": [("SKU-014", 1), ("SKU-017", 5)],
                    "status": "confirmed",
                    "order_status": "confirmed",
                    "total": 185,
                    "queue_len": 0,
                    "stocks": {"SKU-014": 59, "SKU-017": 195},
                },
            },
        ],
    },
    {
        "id": "official-4-surf-consent",
        "title": "Surf Excel is out of stock and is not swapped until consent",
        "customer_id": "C003",
        "source": "Section 6, scenario 4",
        "turns": [
            {
                "message": "2 Surf Excel 1kg",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "Surf Excel 1kg", "quantity": 2, "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [],
                    "status": "substituting",
                    "substitutions": [("SKU-029", ["SKU-030", "SKU-031"])],
                    "order_status": None,
                    "stocks": {"SKU-029": 0, "SKU-030": 30, "SKU-031": 12},
                },
            },
            {
                "message": "Tide Plus",
                "nlu": {
                    "intent": "accept_substitution",
                    "mentions": [],
                    "accepted_substitute": "Tide Plus",
                },
                "expect": {
                    "cart": [("SKU-030", 2)],
                    "status": "awaiting_customer_confirmation",
                    "total": 230,
                    "substitutions": [],
                    "order_status": None,
                    "stocks": {"SKU-029": 0, "SKU-030": 30},
                },
            },
        ],
    },
    {
        "id": "official-5-credit-approval",
        "title": "Suresh exceeds his credit limit, then Ramesh approves",
        "customer_id": "C001",
        "source": "Section 6, scenario 5",
        "turns": [
            {
                "message": (
                    "Aashirvaad 5 kg atta, 2 kg toor dal, 1 litre Fortune oil "
                    "aur 1 Tata Tea Gold bhej do"
                ),
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "Aashirvaad 5 kg atta", "quantity": 1, "action": "add"},
                        {"description": "toor dal", "quantity": 2, "unit": "kg", "action": "add"},
                        {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
                        {"description": "Tata Tea Gold", "quantity": 1, "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [
                        ("SKU-005", 1),
                        ("SKU-009", 2),
                        ("SKU-014", 1),
                        ("SKU-023", 1),
                    ],
                    "status": "awaiting_customer_confirmation",
                    "total": 880,
                    "approval_required": True,
                    "approval_reasons": ["Customer credit limit exceeded"],
                    "order_status": None,
                    "outstanding": 4800,
                    "stocks": {"SKU-005": 25},
                },
            },
            {
                "message": "haan, confirm",
                "nlu": {"intent": "confirm", "mentions": []},
                "expect": {
                    "cart": [
                        ("SKU-005", 1),
                        ("SKU-009", 2),
                        ("SKU-014", 1),
                        ("SKU-023", 1),
                    ],
                    "status": "awaiting_owner_approval",
                    "order_status": "awaiting_owner_approval",
                    "total": 880,
                    "queue_len": 1,
                    "approval_reasons_on_queue": ["Customer credit limit exceeded"],
                    "recommendation_present": True,
                    "outstanding": 4800,
                    "stocks": {"SKU-005": 25, "SKU-014": 60},
                },
            },
            {
                "action": "owner_approve",
                "expect": {
                    "status": "confirmed",
                    "order_status": "confirmed",
                    "queue_len": 0,
                    "outstanding": 5680,
                    "stocks": {"SKU-005": 24, "SKU-009": 78, "SKU-014": 59, "SKU-023": 29},
                },
            },
        ],
    },
    {
        "id": "official-6-chini-tel",
        "title": "Chini resolves to sugar; tel stays ambiguous across three oils",
        "customer_id": "C002",
        "source": "Section 6, scenario 6",
        "turns": [
            {
                "message": "chini 2 kilo aur tel ek litre",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "chini", "quantity": 2, "unit": "kilo", "action": "add"},
                        {"description": "tel", "quantity": 1, "unit": "litre", "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [("SKU-001", 2)],
                    "status": "clarifying",
                    "clarification_skus": ["SKU-014", "SKU-015", "SKU-016"],
                    "order_status": None,
                    "stocks": {"SKU-001": 120, "SKU-014": 60},
                },
            }
        ],
    },
    {
        "id": "official-7-paneer",
        "title": "Paneer is unsupported; Lay's continues",
        "customer_id": "C006",
        "source": "Section 6, scenario 7",
        "turns": [
            {
                "message": "1 kg paneer aur 2 Lay's",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "paneer", "quantity": 1, "unit": "kg", "action": "add"},
                        {"description": "Lay's", "quantity": 2, "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [("SKU-022", 2)],
                    "unsupported_contains": "paneer",
                    "status": "awaiting_customer_confirmation",
                    "total": 40,
                    "clarification": False,
                    "substitutions": [],
                    "order_status": None,
                    "stocks": {"SKU-022": 50},
                },
            }
        ],
    },
    {
        "id": "official-8-modify-order",
        "title": "Rice quantity changes to 10 kg and biscuits are removed",
        "customer_id": "C002",
        "source": "Section 6, scenario 8",
        "turns": [
            {
                "message": "5 kg Sona Masoori rice and 2 Parle-G",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "Sona Masoori rice", "quantity": 5, "unit": "kg", "action": "add"},
                        {"description": "Parle-G", "quantity": 2, "unit": "pack", "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [("SKU-002", 5), ("SKU-017", 2)],
                    "total": 330,
                    "status": "awaiting_customer_confirmation",
                    "stocks": {"SKU-002": 150, "SKU-017": 200},
                },
            },
            {
                "message": "rice 10 kg kar do, biscuits cancel",
                "nlu": {
                    "intent": "modify",
                    "mentions": [
                        {"description": "rice", "quantity": 10, "unit": "kg", "action": "set_quantity"},
                        {"description": "biscuits", "quantity": None, "unit": None, "action": "remove"},
                    ],
                },
                "expect": {
                    "cart": [("SKU-002", 10)],
                    "total": 620,
                    "status": "awaiting_customer_confirmation",
                    "clarification": False,
                    "stocks": {"SKU-002": 150, "SKU-017": 200},
                },
            },
        ],
    },
    {
        "id": "extra-duplicate-confirm",
        "title": "A second confirmation does not deduct stock again",
        "customer_id": "C006",
        "source": "Added failure mode: duplicate confirmation",
        "turns": [
            {
                "message": "1 litre Fortune oil and 5 Parle-G",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "Fortune oil", "quantity": 1, "unit": "L", "action": "add"},
                        {"description": "Parle-G", "quantity": 5, "unit": "pack", "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [("SKU-014", 1), ("SKU-017", 5)],
                    "total": 185,
                    "order_status": None,
                    "stocks": {"SKU-014": 60},
                },
            },
            {
                "message": "haan, confirm",
                "nlu": {"intent": "confirm", "mentions": []},
                "expect": {
                    "status": "confirmed",
                    "order_status": "confirmed",
                    "stocks": {"SKU-014": 59, "SKU-017": 195},
                },
            },
            {
                "message": "haan, confirm",
                "nlu": {"intent": "confirm", "mentions": []},
                "expect": {
                    "status": "confirmed",
                    "same_order": True,
                    "queue_len": 0,
                    "stocks": {"SKU-014": 59, "SKU-017": 195},
                },
            },
        ],
    },
    {
        "id": "extra-reject-substitution",
        "title": "Declining a substitute does not add Tide or Ariel",
        "customer_id": "C003",
        "source": "Added failure mode: substitution without consent",
        "turns": [
            {
                "message": "2 Surf Excel 1kg",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "Surf Excel 1kg", "quantity": 2, "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [],
                    "substitutions": [("SKU-029", ["SKU-030", "SKU-031"])],
                    "stocks": {"SKU-030": 30, "SKU-031": 12},
                },
            },
            {
                "message": "no, don't replace it",
                "nlu": {"intent": "reject_substitution", "mentions": []},
                "expect": {
                    "cart": [],
                    "substitutions": [],
                    "status": "collecting",
                    "order_status": None,
                    "stocks": {"SKU-029": 0, "SKU-030": 30, "SKU-031": 12},
                },
            },
        ],
    },
    {
        "id": "extra-maggi-shortage",
        "title": "Four Maggi are short; Yippee is added only after consent",
        "customer_id": "C006",
        "source": "Added failure mode: stock shortage",
        "turns": [
            {
                "message": "4 Maggi noodles",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "Maggi noodles", "quantity": 4, "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [],
                    "status": "substituting",
                    "substitutions": [("SKU-020", ["SKU-021"])],
                    "stocks": {"SKU-020": 3, "SKU-021": 40},
                },
            },
            {
                "message": "Yippee",
                "nlu": {
                    "intent": "accept_substitution",
                    "mentions": [],
                    "accepted_substitute": "Yippee",
                },
                "expect": {
                    "cart": [("SKU-021", 4)],
                    "total": 56,
                    "order_status": None,
                    "stocks": {"SKU-020": 3, "SKU-021": 40},
                },
            },
            {
                "message": "haan, confirm",
                "nlu": {"intent": "confirm", "mentions": []},
                "expect": {
                    "cart": [("SKU-021", 4)],
                    "status": "confirmed",
                    "order_status": "confirmed",
                    "total": 56,
                    "stocks": {"SKU-020": 3, "SKU-021": 36},
                },
            },
        ],
    },
    {
        "id": "extra-cash-over-3000",
        "title": "A cash order above Rs.3000 waits for Ramesh and does not reserve stock",
        "customer_id": "C002",
        "source": "Added failure mode: large order approval",
        "turns": [
            {
                "message": "50 kg Sona Masoori rice",
                "nlu": {
                    "intent": "new_order",
                    "mentions": [
                        {"description": "Sona Masoori rice", "quantity": 50, "unit": "kg", "action": "add"},
                    ],
                },
                "expect": {
                    "cart": [("SKU-002", 50)],
                    "total": 3100,
                    "approval_required": True,
                    "approval_reasons": ["Order exceeds Rs. 3000"],
                    "status": "awaiting_customer_confirmation",
                    "stocks": {"SKU-002": 150},
                },
            },
            {
                "message": "haan, confirm",
                "nlu": {"intent": "confirm", "mentions": []},
                "expect": {
                    "status": "awaiting_owner_approval",
                    "order_status": "awaiting_owner_approval",
                    "queue_len": 1,
                    "approval_reasons_on_queue": ["Order exceeds Rs. 3000"],
                    "recommendation_present": True,
                    "outstanding": 0,
                    "stocks": {"SKU-002": 150},
                },
            },
        ],
    },
]
