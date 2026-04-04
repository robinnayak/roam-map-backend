from rest_framework import serializers

from .models import PackingItem
from .services import get_next_sort_order, normalize_checklist_text


class PackingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackingItem
        fields = [
            'id',
            'name',
            'category',
            'is_checked',
            'note',
            'sort_order',
            'is_default',
        ]
        read_only_fields = ['id', 'is_default']

    def validate_name(self, value):
        normalized = normalize_checklist_text(value)
        if not normalized:
            raise serializers.ValidationError('Name is required.')
        return normalized

    def validate_category(self, value):
        normalized = normalize_checklist_text(value)
        if not normalized:
            raise serializers.ValidationError('Category is required.')
        return normalized

    def validate_note(self, value):
        return value.strip()

    def create(self, validated_data):
        user = self.context['user']
        if 'sort_order' not in validated_data:
            validated_data['sort_order'] = get_next_sort_order(user, validated_data['category'])
        return PackingItem.objects.create(user=user, **validated_data)


class ChecklistCategorySerializer(serializers.Serializer):
    category = serializers.CharField()
    packed_count = serializers.IntegerField()
    total_count = serializers.IntegerField()
    items = PackingItemSerializer(many=True)


class ChecklistGroupedResponseSerializer(serializers.Serializer):
    packed_count = serializers.IntegerField()
    total_count = serializers.IntegerField()
    categories = ChecklistCategorySerializer(many=True)

