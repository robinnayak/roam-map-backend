from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .consumers import broadcast_direct_message
from .models import Conversation, DirectMessage, users_have_accepted_connection
from .serializers import ChatUserSerializer, DirectMessageSerializer, SendDirectMessageSerializer

User = get_user_model()


class ChatAccessMixin:
    def get_other_user(self, user_id):
        return get_object_or_404(User, id=user_id)

    def get_connected_other_user(self, request, user_id):
        other_user = self.get_other_user(user_id)
        if not users_have_accepted_connection(request.user.id, other_user.id):
            return None, Response(
                {'detail': 'Direct messages are only available for accepted connections.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return other_user, None

    def get_conversation(self, request_user, other_user):
        conversation, _ = Conversation.get_or_create_for_users(request_user, other_user)
        return conversation


class ConversationHistoryView(ChatAccessMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    page_size = 50

    def get(self, request, user_id):
        other_user, error_response = self.get_connected_other_user(request, user_id)
        if error_response is not None:
            return error_response

        conversation = self.get_conversation(request.user, other_user)
        queryset = conversation.messages.select_related('sender', 'recipient').order_by('created_at', 'id')

        page_number = request.query_params.get('page', 1)
        paginator = Paginator(queryset, self.page_size)
        page = paginator.get_page(page_number)
        serializer = DirectMessageSerializer(page.object_list, many=True)

        payload = {
            'conversation_id': conversation.id,
            'other_user': ChatUserSerializer(other_user).data,
            'unread_count': conversation.messages.filter(
                recipient=request.user,
                is_read=False,
            ).count(),
            'count': paginator.count,
            'next': page.next_page_number() if page.has_next() else None,
            'previous': page.previous_page_number() if page.has_previous() else None,
            'results': serializer.data,
        }
        return Response(payload, status=status.HTTP_200_OK)


class SendDirectMessageView(ChatAccessMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        serializer = SendDirectMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        other_user, error_response = self.get_connected_other_user(request, user_id)
        if error_response is not None:
            return error_response

        with transaction.atomic():
            conversation = self.get_conversation(request.user, other_user)
            message = DirectMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                recipient=other_user,
                body=serializer.validated_data['body'],
            )
            conversation.save(update_fields=['updated_at'])

        serialized_message = DirectMessageSerializer(message).data
        broadcast_direct_message(conversation.id, serialized_message)
        return Response(serialized_message, status=status.HTTP_201_CREATED)


class MarkConversationReadView(ChatAccessMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, user_id):
        other_user, error_response = self.get_connected_other_user(request, user_id)
        if error_response is not None:
            return error_response

        conversation = self.get_conversation(request.user, other_user)
        updated_count = conversation.messages.filter(
            sender=other_user,
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)

        return Response(
            {
                'conversation_id': conversation.id,
                'marked_read': updated_count,
            },
            status=status.HTTP_200_OK,
        )

