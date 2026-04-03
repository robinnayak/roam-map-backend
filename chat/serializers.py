from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Conversation, DirectMessage

User = get_user_model()


class ChatUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name')


class DirectMessageSerializer(serializers.ModelSerializer):
    sender = ChatUserSerializer(read_only=True)
    recipient = ChatUserSerializer(read_only=True)

    class Meta:
        model = DirectMessage
        fields = ('id', 'conversation', 'sender', 'recipient', 'body', 'created_at', 'is_read')
        read_only_fields = ('id', 'conversation', 'sender', 'recipient', 'created_at', 'is_read')


class SendDirectMessageSerializer(serializers.Serializer):
    body = serializers.CharField(allow_blank=False, trim_whitespace=True)

    def validate_body(self, value):
        body = value.strip()
        if not body:
            raise serializers.ValidationError('Message body cannot be empty.')
        return body


class ConversationHistorySerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField()
    other_user = ChatUserSerializer()
    unread_count = serializers.IntegerField()
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = DirectMessageSerializer(many=True)


class ConversationEnvelopeSerializer(serializers.Serializer):
    type = serializers.CharField()
    message = DirectMessageSerializer()

