from django.db import models

from users.models import TenantUser


class GenericModel(models.Model):
    """
    A base model that can be used to create generic models.
    """
    created_by = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name='%(class)s_created_by',
        null=True,
        blank=True
    )
    updated_by = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name='%(class)s_updated_by',
        null=True,
        blank=True
    )
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    is_hidden = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.__class__.__name__} - {self.pk}"