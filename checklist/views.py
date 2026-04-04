from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PackingItem
from .serializers import ChecklistGroupedResponseSerializer, PackingItemSerializer
from .services import build_grouped_checklist_payload, seed_default_items_for_user


def get_user_checklist_payload(user):
    items = PackingItem.objects.filter(user=user).order_by('category', 'sort_order', 'id')
    payload = build_grouped_checklist_payload(items)
    return ChecklistGroupedResponseSerializer(payload).data


class ChecklistListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(get_user_checklist_payload(request.user), status=status.HTTP_200_OK)

    def post(self, request):
        serializer = PackingItemSerializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(PackingItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ChecklistItemDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, user, item_id):
        return PackingItem.objects.filter(user=user, id=item_id).first()

    def patch(self, request, item_id):
        item = self.get_object(request.user, item_id)
        if item is None:
            return Response({'detail': 'Checklist item not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PackingItemSerializer(
            item,
            data=request.data,
            partial=True,
            context={'user': request.user},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PackingItemSerializer(item).data, status=status.HTTP_200_OK)

    def delete(self, request, item_id):
        item = self.get_object(request.user, item_id)
        if item is None:
            return Response({'detail': 'Checklist item not found.'}, status=status.HTTP_404_NOT_FOUND)

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChecklistResetView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        reset_count = PackingItem.objects.filter(user=request.user, is_checked=True).update(is_checked=False)
        return Response(
            {
                'reset_count': reset_count,
                'checklist': get_user_checklist_payload(request.user),
            },
            status=status.HTTP_200_OK,
        )


class ChecklistSeedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        seeded = seed_default_items_for_user(request.user)
        return Response(
            {
                'seeded': seeded,
                'checklist': get_user_checklist_payload(request.user),
            },
            status=status.HTTP_200_OK,
        )

