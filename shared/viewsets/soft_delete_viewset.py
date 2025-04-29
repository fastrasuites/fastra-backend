from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response


class SoftDeleteWithModelViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin,
                                 mixins.RetrieveModelMixin, mixins.UpdateModelMixin):
    """
    A viewset that provides default `list()`, `create()`, `retrieve()`, `update()`, `partial_update()`,
    and a custom `destroy()` action to hide instances instead of deleting them, a custom action to list
    hidden instances, a custom action to revert the hidden field back to False.
    """

    def get_queryset(self):
        # # Filter out hidden instances by default
        # return self.queryset.filter(is_hidden=False)
        return super().get_queryset()

    @action(detail=True, methods=['put', 'patch'])
    def toggle_hidden_status(self, request, pk=None, *args, **kwargs):
        # Toggle the hidden status of an instance
        instance = self.get_object()
        instance.is_hidden = not instance.is_hidden
        instance.save()
        return Response({'status': f'Hidden status set to {instance.is_hidden}'}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['delete'])
    def soft_delete(self, request, pk=None, *args, **kwargs):
        # Soft delete an instance
        instance = self.get_object()
        instance.is_hidden = True
        instance.save()
        return Response({'status': 'hidden'}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def hidden_list(self, request, *args, **kwargs):
        # List all hidden instances
        hidden_instances = self.queryset.filter(is_hidden=True)
        page = self.paginate_queryset(hidden_instances)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(hidden_instances, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def active_list(self, request, *args, **kwargs):
        # List all active instances
        active_instances = self.queryset.filter(is_hidden=False)
        page = self.paginate_queryset(active_instances)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(active_instances, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)