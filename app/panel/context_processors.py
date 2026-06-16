from core.models import Sale


def pending_count(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return {}
    return {"pending_count": Sale.objects.filter(status=Sale.Status.PENDING).count()}
