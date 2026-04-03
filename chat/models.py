from django.conf import settings
from django.db import models
from django.db.models import Q

from users.models import UserConnection, get_connection_lookup


class ConversationQuerySet(models.QuerySet):
    def for_user_pair(self, user_a_id, user_b_id):
        user_one_id, user_two_id = Conversation.normalize_user_ids(user_a_id, user_b_id)
        return self.filter(user_one_id=user_one_id, user_two_id=user_two_id)


class Conversation(models.Model):
    user_one = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_conversations_as_user_one',
    )
    user_two = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_conversations_as_user_two',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ConversationQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user_one', 'user_two'],
                name='unique_conversation_user_pair',
            ),
            models.CheckConstraint(
                check=~Q(user_one=models.F('user_two')),
                name='prevent_self_conversation',
            ),
        ]
        indexes = [
            models.Index(fields=['user_one', 'user_two']),
            models.Index(fields=['updated_at']),
        ]

    def save(self, *args, **kwargs):
        self.user_one_id, self.user_two_id = self.normalize_user_ids(
            self.user_one_id,
            self.user_two_id,
        )
        super().save(*args, **kwargs)

    @staticmethod
    def normalize_user_ids(user_a_id, user_b_id):
        if user_a_id == user_b_id:
            return user_a_id, user_b_id
        return tuple(sorted((user_a_id, user_b_id)))

    @classmethod
    def get_or_create_for_users(cls, user_a, user_b):
        return cls.get_or_create_for_user_ids(user_a.id, user_b.id)

    @classmethod
    def get_or_create_for_user_ids(cls, user_a_id, user_b_id):
        user_one_id, user_two_id = cls.normalize_user_ids(user_a_id, user_b_id)
        defaults = {
            'user_one_id': user_one_id,
            'user_two_id': user_two_id,
        }
        return cls.objects.get_or_create(
            user_one_id=user_one_id,
            user_two_id=user_two_id,
            defaults=defaults,
        )

    def includes_user(self, user_id):
        return user_id in {self.user_one_id, self.user_two_id}

    def other_user_id(self, user_id):
        return self.user_two_id if self.user_one_id == user_id else self.user_one_id

    def __str__(self):
        return f'Conversation({self.user_one_id}, {self.user_two_id})'


class DirectMessage(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_direct_messages',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_direct_messages',
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['conversation', 'created_at', 'id']),
            models.Index(fields=['recipient', 'is_read']),
        ]

    def save(self, *args, **kwargs):
        if self.conversation_id:
            participants = {self.conversation.user_one_id, self.conversation.user_two_id}
            if self.sender_id not in participants or self.recipient_id not in participants:
                raise ValueError('Message participants must belong to the conversation.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'DirectMessage({self.sender_id} -> {self.recipient_id})'


def users_have_accepted_connection(user_a_id, user_b_id):
    return UserConnection.objects.filter(
        get_connection_lookup(user_a_id, user_b_id),
        status=UserConnection.Status.ACCEPTED,
    ).exists()
