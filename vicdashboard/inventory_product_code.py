"""Auto-generate inventory product codes from category."""

from __future__ import annotations

import re

from .models import InventoryCategory, InventoryItem

# Keep generated codes within InventoryItem.product_code max_length.
PRODUCT_CODE_MAX_LENGTH = 100
PRODUCT_CODE_SEQ_WIDTH = 3


def category_product_prefix(category: InventoryCategory | None) -> str:
    """Build a stable code prefix from the selected category name."""
    if category is None:
        return 'PRD'
    name = (category.name or '').upper().strip()
    slug = re.sub(r'[^A-Z0-9]+', '-', name).strip('-')
    prefix = slug or 'PRD'
    # Reserve "-###" for the sequence suffix.
    max_prefix = PRODUCT_CODE_MAX_LENGTH - (PRODUCT_CODE_SEQ_WIDTH + 1)
    if len(prefix) > max_prefix:
        prefix = prefix[:max_prefix].rstrip('-') or 'PRD'
    return prefix


def generate_inventory_product_code(
    category: InventoryCategory | None,
    exclude_item_id: int | None = None,
) -> str:
    """Return the next product code for a category, e.g. COUPLING-001."""
    prefix = category_product_prefix(category)
    qs = InventoryItem.objects.filter(category=category)
    if exclude_item_id:
        qs = qs.exclude(pk=exclude_item_id)

    max_num = 0
    pattern = re.compile(rf'^{re.escape(prefix)}-(\d+)$', re.IGNORECASE)
    for code in qs.values_list('product_code', flat=True):
        text = (code or '').strip()
        if not text:
            continue
        match = pattern.match(text)
        if match:
            max_num = max(max_num, int(match.group(1)))

    return f'{prefix}-{max_num + 1:0{PRODUCT_CODE_SEQ_WIDTH}d}'


def next_product_codes_by_category() -> dict[int, str]:
    """Preview map of category id -> next suggested product code."""
    return {
        category.id: generate_inventory_product_code(category)
        for category in InventoryCategory.objects.all()
    }
