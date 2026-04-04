from collections import defaultdict

from .constants import CHECKLIST_CATEGORY_ORDER, DEFAULT_PACKING_ITEMS
from .models import PackingItem


def normalize_checklist_text(value: str) -> str:
    return ' '.join(value.split()).strip()


def seed_default_items_for_user(user):
    if PackingItem.objects.filter(user=user).exists():
        return False

    category_counts = defaultdict(int)
    items_to_create = []
    for item in DEFAULT_PACKING_ITEMS:
        category = normalize_checklist_text(item['category'])
        category_counts[category] += 1
        items_to_create.append(
            PackingItem(
                user=user,
                category=category,
                name=normalize_checklist_text(item['name']),
                note=item.get('note', '').strip(),
                sort_order=category_counts[category],
                is_default=True,
            )
        )

    PackingItem.objects.bulk_create(items_to_create)
    return True


def get_next_sort_order(user, category: str) -> int:
    normalized_category = normalize_checklist_text(category)
    last_item = (
        PackingItem.objects.filter(user=user, category=normalized_category)
        .order_by('-sort_order', '-id')
        .first()
    )
    if last_item is None:
        return 1
    return last_item.sort_order + 1


def build_grouped_checklist_payload(items):
    grouped_items = defaultdict(list)
    for item in items:
        grouped_items[item.category].append(item)

    ordered_categories = [category for category in CHECKLIST_CATEGORY_ORDER if category in grouped_items]
    ordered_categories.extend(
        sorted(category for category in grouped_items if category not in CHECKLIST_CATEGORY_ORDER)
    )

    categories = []
    packed_count = 0
    total_count = 0
    for category in ordered_categories:
        category_items = grouped_items[category]
        category_packed_count = sum(1 for item in category_items if item.is_checked)
        packed_count += category_packed_count
        total_count += len(category_items)
        categories.append(
            {
                'category': category,
                'packed_count': category_packed_count,
                'total_count': len(category_items),
                'items': category_items,
            }
        )

    return {
        'packed_count': packed_count,
        'total_count': total_count,
        'categories': categories,
    }

