from django.contrib import admin, messages
from django.db import models
from django.db.models import Count
from django.utils.html import format_html

from . import services
from .exports import PARTICIPANT_COLUMNS, SALE_COLUMNS, TICKET_COLUMNS, export_xlsx
from .models import AuditLog, Campaign, Draw, Participant, Sale, Ticket


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "full_name", "phone", "salon", "factory", "city",
        "sales_approved", "tickets_count", "bonus_total", "created_at", "is_blocked",
    )
    list_filter = ("city", "factory", "is_blocked")
    search_fields = ("full_name", "phone", "salon", "factory", "city")
    actions = ("export_excel",)

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .annotate(_tickets=Count("tickets", distinct=True))
        )

    @admin.display(description="Підтв. продажів")
    def sales_approved(self, obj):
        return obj.sales.filter(status=Sale.Status.APPROVED).count()

    @admin.display(description="Квитків", ordering="_tickets")
    def tickets_count(self, obj):
        return obj._tickets

    @admin.display(description="Бонуси, грн")
    def bonus_total(self, obj):
        total = obj.sales.filter(status=Sale.Status.APPROVED).aggregate(
            s=models.Sum("bonus_amount")
        )["s"]
        return total or 0

    @admin.action(description="Експорт у Excel")
    def export_excel(self, request, queryset):
        return export_xlsx(queryset, PARTICIPANT_COLUMNS, "veloro_participants")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "id", "created_at", "participant", "salon", "city",
        "sale_date", "product_display", "fabric_name",
        "status", "moderated_by",
    )
    list_filter = ("status", "campaign", "sale_date")
    search_fields = (
        "participant__full_name", "participant__salon",
        "participant__city", "fabric_name",
    )
    readonly_fields = (
        "participant", "campaign", "created_at", "doc_photo_preview",
        "product_photo_preview", "moderated_by", "moderated_at",
    )
    actions = ("approve_selected", "export_excel")
    date_hierarchy = "sale_date"

    @admin.display(description="Салон")
    def salon(self, obj):
        return obj.participant.salon

    @admin.display(description="Фабрика")
    def factory(self, obj):
        return obj.participant.factory

    @admin.display(description="Місто")
    def city(self, obj):
        return obj.participant.city

    @admin.display(description="Виріб")
    def product_display(self, obj):
        return obj.product_display

    @admin.display(description="Фото документа")
    def doc_photo_preview(self, obj):
        if obj.doc_photo:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height:300px"></a>',
                obj.doc_photo.url,
            )
        return "—"

    @admin.display(description="Фото виробу")
    def product_photo_preview(self, obj):
        if obj.product_photo:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height:300px"></a>',
                obj.product_photo.url,
            )
        return "—"

    @admin.action(description="✅ Підтвердити вибрані продажі (нарахувати квитки)")
    def approve_selected(self, request, queryset):
        approved = 0
        for sale in queryset.filter(status=Sale.Status.PENDING):
            result, _ = services.approve_sale(sale.id, f"admin:{request.user.username}")
            if result:
                approved += 1
        self.message_user(request, f"Підтверджено продажів: {approved}.", messages.SUCCESS)

    @admin.action(description="Експорт у Excel")
    def export_excel(self, request, queryset):
        return export_xlsx(queryset.select_related("participant"), SALE_COLUMNS, "veloro_sales")

    def has_delete_permission(self, request, obj=None):
        # видалення підтверджених продажів — лише суперадміністратор
        if obj is not None and obj.status == Sale.Status.APPROVED:
            return request.user.is_superuser
        return super().has_delete_permission(request, obj)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("code", "participant", "sale", "campaign", "created_at")
    search_fields = ("participant__full_name", "participant__salon")
    list_filter = ("campaign",)
    actions = ("export_excel",)

    def has_add_permission(self, request):
        return False  # квитки створюються лише підтвердженням продажу

    @admin.action(description="Експорт у Excel")
    def export_excel(self, request, queryset):
        return export_xlsx(
            queryset.select_related("participant", "sale"), TICKET_COLUMNS, "veloro_tickets"
        )


@admin.register(Draw)
class DrawAdmin(admin.ModelAdmin):
    """Створення запису «Розіграш» = проведення розіграшу."""
    list_display = (
        "prize", "campaign", "performed_at", "winning_ticket",
        "winner", "tickets_total", "performed_by",
    )
    actions = ("broadcast_results",)

    def get_readonly_fields(self, request, obj=None):
        if obj:  # результат зафіксовано, редагувати не можна
            return ("campaign", "prize")
        return ()

    def save_model(self, request, obj, form, change):
        if change:
            return
        actor = f"admin:{request.user.username}"
        try:
            services.perform_draw(obj, actor)
        except services.DrawError as e:
            self.message_user(request, str(e), messages.ERROR)
            return
        services.notify_winner(obj)
        self.message_user(
            request,
            f"Розіграш проведено! Виграшний квиток {obj.winning_ticket.code}, "
            f"переможець: {obj.winner.full_name}. Переможця сповіщено.",
            messages.SUCCESS,
        )

    @admin.action(description="📣 Розіслати результати всім учасникам")
    def broadcast_results(self, request, queryset):
        for draw in queryset.filter(winner__isnull=False):
            sent = services.broadcast_draw_results(draw, f"admin:{request.user.username}")
            self.message_user(
                request, f"«{draw.prize}»: розіслано {sent} учасникам.", messages.SUCCESS
            )

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "details")
    list_filter = ("action",)
    search_fields = ("actor", "action")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
