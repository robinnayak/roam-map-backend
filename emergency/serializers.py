from rest_framework import serializers

from groups.models import GroupMembership

from .models import SOSAlert


class SOSAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = SOSAlert
        fields = [
            'id',
            'user',
            'group',
            'latitude',
            'longitude',
            'triggered_at',
            'resolved_at',
            'is_active',
        ]
        read_only_fields = ['id', 'user', 'resolved_at', 'is_active']

    def validate_group(self, group):
        request = self.context.get('request')
        if request is None or request.user.is_anonymous:
            raise serializers.ValidationError('Authentication is required.')

        is_member = GroupMembership.objects.filter(group=group, user=request.user).exists()
        if not is_member:
            raise serializers.ValidationError('You are not a member of this group.')
        return group

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['is_active'] = True
        validated_data['resolved_at'] = None
        return super().create(validated_data)
