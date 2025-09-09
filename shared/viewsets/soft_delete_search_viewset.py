from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, filters, viewsets, mixins
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.response import Response

from users.models import TenantUser


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

    # def list(self, request, *args, **kwargs):
    #     page = int(request.query_params.get('page', 1))
    #     page_size = int(request.query_params.get('page_size', 10))
    #     order = request.query_params.get('order', 'asc')
    #     ordering = '' if order == 'asc' else '-'
    #     queryset = self.filter_queryset(self.get_queryset())
    #     # Assuming 'id' is the field to order by; change as needed
    #     # order_by = request.query_params.get('order_by', 'id')
    #     # if order_by not in ['id', 'created_at', 'updated_at']:
    #     #     return Response({'error': 'Invalid order_by field'}, status=status.HTTP_400_BAD_REQUEST)
    #     queryset = queryset.order_by(f'{ordering}{self.queryset.model._meta.pk.name}')
    #     total_records = queryset.count()
    #     paginator = PageNumberPagination()
    #     paginator.page_size = page_size
    #     paginated_queryset = paginator.paginate_queryset(queryset, request)
    #     total_page_records = len(paginated_queryset)
    #     serializer = self.get_serializer(paginated_queryset, many=True)
    #     return Response({
    #         "page": str(page),
    #         "total": str(total_page_records),
    #         "records": str(total_records),
    #         "rows": serializer.data
    #     }, status=status.HTTP_200_OK)
    #
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        current_id = instance.pk
        # Find the next instance by pk
        next_instance = self.get_queryset().filter(pk__gt=current_id).order_by(f'{self.queryset.model._meta.pk.name}').first()
        prev_instance = self.get_queryset().filter(pk__lt=current_id).order_by(f'-{self.queryset.model._meta.pk.name}').first()
        total_records = self.get_queryset().count()
        prev_id = prev_instance.pk if prev_instance else None
        next_id = next_instance.pk if next_instance else None
        data = serializer.data
        data['next_id'] = next_id
        data['prev_id'] = prev_id
        data['total_records'] = total_records
        return Response(data, status=status.HTTP_200_OK)


    # def list(self, request, *args, **kwargs):
    #     queryset = self.get_queryset()
    #     paginator = PageNumberPagination()
    #     paginator.page_size = 10  # Items per page
    #     paginated_queryset = paginator.paginate_queryset(queryset, request)
    #     serializer = self.get_serializer(paginated_queryset, many=True)
    #     return paginator.get_paginated_response(serializer.data)

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
        if instance.is_hidden:
            return Response({'error': 'Instance is already hidden'}, status=status.HTTP_400_BAD_REQUEST)
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


class SearchDeleteViewSet(SoftDeleteWithModelViewSet):
    """
    A viewset that inherits from `SoftDeleteWithModelViewSet` and adds a custom `search` action to
    enable searching functionality.
    The search functionality can be accessed via the DRF API interface.
    """
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = []
    filterset_fields = []


class SearchDeleteViewSetWithCreatedUpdated(SearchDeleteViewSet):

    def perform_create(self, serializer):
        user = self.request.user
        tenant_user = TenantUser.objects.filter(user=user, is_hidden=False).first()
        serializer.save(created_by=tenant_user)

    def perform_update(self, serializer):
        user = self.request.user
        tenant_user = TenantUser.objects.filter(user=user, is_hidden=False).first()
        serializer.save(updated_by=tenant_user)


class SearchViewSet(viewsets.ModelViewSet):
    """
    A viewset that inherits from the regular `viewsets.ModelViewSet` and adds a custom `search` action to
    enable searching functionality.
    The search functionality can be accessed via the DRF API interface.
    """
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = []
    filterset_fields = []


class NoCreateSearchViewSet(SearchDeleteViewSet):
    """
    A viewset that inherits from `SearchDeleteViewSet` and removes the `create` action.
    This is useful for read-only APIs where creation of new instances is not allowed.
    """
    def create(self, request, *args, **kwargs):
        return Response({'error': 'Creation of new instances is not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)