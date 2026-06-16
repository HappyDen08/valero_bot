from django.db import models


class Campaign(models.Model):
    name = models.CharField("Назва", max_length=200)
    start_date = models.DateField("Початок акції")
    end_date = models.DateField("Дедлайн подачі продажів")
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Кампанія"
        verbose_name_plural = "Кампанії"

    def __str__(self):
        return self.name

    @classmethod
    def current(cls):
        return cls.objects.filter(is_active=True).order_by("-start_date").first()


class Participant(models.Model):
    telegram_id = models.BigIntegerField("Telegram ID", unique=True)
    full_name = models.CharField("ПІБ", max_length=200)
    phone = models.CharField("Телефон", max_length=32)
    salon = models.CharField("Салон", max_length=200)
    factory = models.CharField("Фабрика", max_length=200, blank=True)
    city = models.CharField("Місто", max_length=100)
    is_blocked = models.BooleanField("Заблокований", default=False)
    created_at = models.DateTimeField("Зареєстрований", auto_now_add=True)

    class Meta:
        verbose_name = "Учасник"
        verbose_name_plural = "Учасники"

    def __str__(self):
        return f"{self.full_name} ({self.salon})"


class Sale(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Очікує перевірки"
        APPROVED = "approved", "Підтверджено"
        REJECTED = "rejected", "Відхилено"

    class ProductType(models.TextChoices):
        SOFA = "sofa", "Диван"
        BED = "bed", "Ліжко"
        CHAIR = "chair", "Крісло"
        OTHER = "other", "Інше"

    # виплата продавцю за підтверджений продаж, грн
    BONUS_RATES = {
        ProductType.SOFA: 150,
        ProductType.BED: 100,
        ProductType.CHAIR: 15,
        ProductType.OTHER: 0,
    }

    participant = models.ForeignKey(
        Participant, on_delete=models.PROTECT, related_name="sales", verbose_name="Учасник"
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.PROTECT, related_name="sales", verbose_name="Кампанія"
    )
    sale_date = models.DateField("Дата продажу")
    product_type = models.CharField(
        "Виріб", max_length=20, choices=ProductType.choices
    )
    product_name = models.CharField("Назва виробу (інше)", max_length=200, blank=True)
    fabric_name = models.CharField("Тканина Veloro", max_length=200)
    doc_photo_file_id = models.CharField("Фото документа (file_id)", max_length=300, blank=True)
    doc_photo = models.FileField("Фото документа", upload_to="sales/", blank=True)
    product_photo_file_id = models.CharField(
        "Фото виробу (file_id)", max_length=300, blank=True
    )
    product_photo = models.FileField("Фото виробу", upload_to="sales/", blank=True)
    amount = models.DecimalField(
        "Сума замовлення", max_digits=12, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    reject_reason = models.TextField("Причина відхилення", blank=True)
    bonus_amount = models.DecimalField(
        "Бонус, грн", max_digits=10, decimal_places=2, default=0,
        help_text="Фіксується в момент підтвердження продажу",
    )
    moderated_by = models.CharField("Модерував", max_length=200, blank=True)
    moderated_at = models.DateTimeField("Час модерації", null=True, blank=True)
    created_at = models.DateTimeField("Подано", auto_now_add=True)

    class Meta:
        verbose_name = "Продаж"
        verbose_name_plural = "Продажі"

    def __str__(self):
        return f"Продаж №{self.pk}"

    @property
    def product_display(self):
        if self.product_type == self.ProductType.OTHER and self.product_name:
            return self.product_name
        return self.get_product_type_display()


class Ticket(models.Model):
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name="tickets", verbose_name="Продаж"
    )
    participant = models.ForeignKey(
        Participant, on_delete=models.PROTECT, related_name="tickets", verbose_name="Учасник"
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.PROTECT, related_name="tickets", verbose_name="Кампанія"
    )
    created_at = models.DateTimeField("Нараховано", auto_now_add=True)

    class Meta:
        verbose_name = "Квиток"
        verbose_name_plural = "Квитки"

    @property
    def code(self):
        return f"#{self.pk:06d}"

    def __str__(self):
        return self.code


class Draw(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.PROTECT, related_name="draws", verbose_name="Кампанія"
    )
    prize = models.CharField("Приз", max_length=200)
    winning_ticket = models.ForeignKey(
        Ticket, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Виграшний квиток", editable=False,
    )
    winner = models.ForeignKey(
        Participant, on_delete=models.PROTECT, null=True, blank=True,
        verbose_name="Переможець", editable=False,
    )
    tickets_total = models.PositiveIntegerField(
        "Квитків у розіграші", default=0, editable=False
    )
    performed_by = models.CharField("Провів", max_length=200, blank=True, editable=False)
    performed_at = models.DateTimeField("Дата і час", auto_now_add=True)

    class Meta:
        verbose_name = "Розіграш"
        verbose_name_plural = "Розіграші"

    def __str__(self):
        return f"{self.prize} — {self.campaign}"

    @property
    def performed_by_display(self):
        # у БД актор зберігається з префіксом джерела ("panel:admin"), показуємо лише нік
        return self.performed_by.split(":", 1)[-1]


class AuditLog(models.Model):
    actor = models.CharField("Хто", max_length=200)
    action = models.CharField("Дія", max_length=100)
    details = models.JSONField("Деталі", default=dict, blank=True)
    created_at = models.DateTimeField("Коли", auto_now_add=True)

    class Meta:
        verbose_name = "Запис журналу"
        verbose_name_plural = "Журнал дій"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%d.%m.%Y %H:%M} {self.actor}: {self.action}"
